# 重力乐园 · 物理设计与运动生成（纯 Python + numpy，不依赖 bpy）
# 思路：timeline.py 给出每个碰撞应落在的拍点 -> 这里用真实物理公式反算几何位置，
# 并生成每个运动物体的轨迹（96 Hz 采样 + 每个碰撞时刻精确插入一个采样点）。
# 骨牌段由 Bullet 仿真（sim_dominoes.py）给出，结果读自 build/domino_sim.npz。
# 坐标：x 向右（机关前进方向），y 向后（远离镜头），z 向上；工作台面 z = 0；单位 m、s、kg。
import math, os, json
import numpy as np
import timeline as TL

G = 9.81
KEY_HZ = 96
N_DOMINO = 56
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")

# ---------------- 通用工具 ----------------
def grid(t0, t1, hz=KEY_HZ):
    a = math.ceil(t0 * hz - 1e-9); b = math.floor(t1 * hz + 1e-9)
    ts = [k / hz for k in range(a, b + 1)]
    return sorted(set([t0] + [x for x in ts if t0 < x < t1] + [t1]))

def pend_quarter(L, phi0, dt=2e-5):
    """大角度单摆：从 phi0（弧度，负=左）静止释放，到 phi=0 所需时间与此时角速度"""
    phi, w, t = phi0, 0.0, 0.0
    while phi < 0:
        def acc(p): return -(G / L) * math.sin(p)
        k1p, k1w = w, acc(phi)
        k2p, k2w = w + .5 * dt * k1w, acc(phi + .5 * dt * k1p)
        k3p, k3w = w + .5 * dt * k2w, acc(phi + .5 * dt * k2p)
        k4p, k4w = w + dt * k3w, acc(phi + dt * k3p)
        phi += dt / 6 * (k1p + 2 * k2p + 2 * k3p + k4p); w += dt / 6 * (k1w + 2 * k2w + 2 * k3w + k4w); t += dt
    return t, w

def pend_curve(L, phi0, T):
    """返回 f(tau)->phi 的插值函数（0..T），用 RK4 积分"""
    dt = 1e-4; ts = [0.0]; ps = [phi0]; phi, w = phi0, 0.0
    n = int(T / dt) + 2
    for i in range(n):
        def acc(p): return -(G / L) * math.sin(p)
        k1p, k1w = w, acc(phi)
        k2p, k2w = w + .5 * dt * k1w, acc(phi + .5 * dt * k1p)
        k3p, k3w = w + .5 * dt * k2w, acc(phi + .5 * dt * k2p)
        k4p, k4w = w + dt * k3w, acc(phi + dt * k3p)
        phi += dt / 6 * (k1p + 2 * k2p + 2 * k3p + k4p); w += dt / 6 * (k1w + 2 * k2w + 2 * k3w + k4w)
        ts.append((i + 1) * dt); ps.append(phi)
    ts = np.array(ts); ps = np.array(ps)
    return lambda tau: float(np.interp(tau, ts, ps))

def solve_L(phi0, tq):
    lo, hi = 0.02, 5.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if pend_quarter(mid, phi0)[0] < tq: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def smooth(u): u = min(1, max(0, u)); return u * u * (3 - 2 * u)

def quat_mul(a, b):
    w1, x1, y1, z1 = a; w2, x2, y2, z2 = b
    return (w1*w2-x1*x2-y1*y2-z1*z2, w1*x2+x1*w2+y1*z2-z1*y2, w1*y2-x1*z2+y1*w2+z1*x2, w1*z2+x1*y2-y1*x2+z1*w2)

# ---------------- 轨迹容器 ----------------
class Track:
    """kind='loc' 位置 + 滚动四元数；kind='rot' 只有绕 y 轴的转角（物体原点在转轴上）；kind='locrot' 位置+y转角"""
    def __init__(self, name, kind="loc", radius=None):
        self.name, self.kind, self.r = name, kind, radius
        self.s = {}   # t -> (loc, roty, rolling)
    def add(self, t, loc=None, roty=0.0, rolling=False):
        self.s[round(t, 7)] = (None if loc is None else tuple(float(v) for v in loc), float(roty), rolling)
    def seg(self, t0, t1, f, rolling=False, extra=()):
        for tt in sorted(set(grid(t0, t1) + [x for x in extra if t0 <= x <= t1])):
            loc, ry = f(tt)
            self.add(tt, loc, ry, rolling)
    def export(self):
        ts = sorted(self.s); out = {"name": self.name, "kind": self.kind, "t": ts}
        if self.kind in ("loc", "locrot"):
            out["loc"] = [self.s[t][0] for t in ts]
        if self.kind in ("rot", "locrot"):
            out["roty"] = [self.s[t][1] for t in ts]
        if self.kind == "loc" and self.r:   # 由速度积分出滚动姿态（四元数）
            q = (1.0, 0.0, 0.0, 0.0); qs = [q]; w = np.zeros(3)
            P = np.array(out["loc"])
            for i in range(1, len(ts)):
                dt = ts[i] - ts[i - 1]
                if dt <= 0: qs.append(q); continue
                v = (P[i] - P[i - 1]) / dt
                if self.s[ts[i]][2]:   # 滚动：omega = z × v / r
                    w = np.array([-v[1], v[0], 0.0]) / self.r
                ang = np.linalg.norm(w) * dt
                if ang > 1e-12:
                    ax = w / np.linalg.norm(w)
                    dq = (math.cos(ang / 2), *(ax * math.sin(ang / 2)))
                    q = quat_mul(dq, q)
                qs.append(q)
            out["quat"] = qs
        return out

CONTACTS = []   # 设计日志：每次碰撞（仅用于校验事件提取，声音不读它）
ROLLS = []      # 持续接触（滚动/滑动）区间：(t0, t1, 物体, 表面材质)
def microhop(t, times, Th):
    """擦碰悬挂管/瓶颈后被轨道约束弹起的微跳：抛体，持续 Th 秒，起跳速度 g*Th/2"""
    for t0 in times:
        tau = t - t0
        if 0 <= tau < Th: return (G * Th / 2) * tau - 0.5 * G * tau * tau
    return 0.0

def contact(t, a, b, kind="hit"): CONTACTS.append(dict(t=float(t), a=a, b=b, kind=kind))

# ---------------- 设计 ----------------
def design():
    CONTACTS.clear(); ROLLS.clear()
    P = {}; T = {}
    # ===== ① 节拍器 + 棘轮 =====
    r1 = 0.0125; P["r_steel"] = r1
    Zs = 1.467                                         # 滚轨起点表面高度
    P["metronome"] = dict(x=-0.30, z=Zs - 0.035, amp=math.radians(24))
    T["metro_arm"] = tr = Track("metro_arm", "rot")
    tr.seg(0, TL.END, lambda t: (None, -P["metronome"]["amp"] * math.sin(2 * math.pi * t)), extra=[k * .5 for k in range(int(TL.END * 2) + 1)])
    for k in range(int(TL.END * 2) + 1):
        contact(TL.TICK0 + k * TL.BEAT, "metro_arm", "metro_body", "tick")
    T["ratchet"] = tr = Track("ratchet", "rot")
    def ratchet(t):
        n = math.floor(t / TL.BEAT + 1e-9); f = (t - n * TL.BEAT) / 0.06
        return None, -math.radians(45) * (n + smooth(f))
    tr.seg(0, TL.END, ratchet, extra=[k * .5 + d for k in range(88) for d in (0, .06)])
    # v5 开场：因果链看得见。棘轮每拍转 45°，轮面上的拨销一拍一拍爬近脱扣杠杆（观众能数到"还差几格"）；
    # 第 5 声（2.0 s）这一格，拨销把杠杆左端顶起 25°，右端压下挡板尾杆，挡板向前翻开 75°，钢珠才开始滚。
    # 杠杆几何与转角互相约束：拨销从 -21° 转到 +10° 抬高约 12 mm（+销半径），左臂 45 mm → 转 18°；
    # 右臂同样压下 14 mm，正好让 14.5 mm 长的挡板尾杆转过 75°
    TRIP_A = math.radians(18); FLAP_D = 0.01; T_GO = TL.RELEASE + 0.03   # 挡板翻过约 15° 时钢珠才动
    P["trip"] = dict(pin_r=0.022, pin_a0=145.0, flap_x=0.014, T_GO=T_GO, tail=0.0145, tip_dz=-0.008)
    T["trip_lever"] = tr = Track("trip_lever", "rot")
    tr.seg(0, TL.END, lambda t: (None, TRIP_A * smooth((t - TL.RELEASE) / 0.06)), extra=[TL.RELEASE, TL.RELEASE + .06])
    contact(TL.RELEASE, "trip_lever", "ratchet", "hit")                  # 脱扣"咔"
    T["flap"] = tr = Track("flap", "rot")
    tr.seg(0, TL.END, lambda t: (None, -math.radians(75) * smooth((t - TL.RELEASE - FLAP_D) / 0.07)), extra=[TL.RELEASE + FLAP_D, TL.RELEASE + FLAP_D + .07])
    contact(TL.RELEASE + FLAP_D, "flap", "ball1", "release")
    # ===== ② 滚轨 =====
    vx = 0.5; h = 0.07; e_bar = 0.4
    tf = math.sqrt(2 * h / G)
    t_edge0 = TL.STAIRS[0][0] - tf
    Trail = t_edge0 - T_GO
    a_r = vx / Trail; Lr = 0.5 * a_r * Trail ** 2
    th = math.asin(a_r * 7 / 5 / G)
    x0 = 0.0; xE0 = x0 + Lr * math.cos(th); Zr = Zs - Lr * math.sin(th)
    P["rail"] = dict(x0=x0 - 0.04, x1=xE0, z0=Zs, z1=Zr, slope_deg=math.degrees(th), a=a_r)
    ball = Track("ball1", "loc", r1); T["ball1"] = ball
    ball.seg(0, T_GO, lambda t: ((x0, 0, Zs + r1), 0))     # 静止靠在挡板上（挡板 x=0.014 = 球半径 + 板厚一半）
    def railpos(t):
        s = 0.5 * a_r * (t - T_GO) ** 2
        return (x0 + s * math.cos(th), 0, Zs - s * math.sin(th) + r1), 0
    ball.seg(T_GO, t_edge0, railpos, rolling=True)
    ROLLS.append((T_GO, t_edge0, "ball1", "maple"))
    # ===== ③ 红木台阶：滚出台阶边 -> 下落 h -> 落在音条上（主音）-> 小弹跳 -> 滚动 -> 下一级 =====
    steps = []
    hc = 0.12; tf7 = math.sqrt(2 * hc / G); t_leave_cup = TL.CUP[0] - tf7
    for k, (tk, note) in enumerate(TL.STAIRS):
        xe = xE0 + 0.25 * k; ztop_prev = Zr - h * k; ztop = Zr - h * (k + 1)
        t_leave = tk - tf
        xl = xe + vx * tf
        steps.append(dict(k=k, x0=xe, x1=xe + 0.25, ztop=ztop, bar_x=xl + 0.025, note=note, t=tk))
        def fly(t, t_leave=t_leave, xe=xe, zp=ztop_prev):
            tau = t - t_leave
            return (xe + vx * tau, 0, zp + r1 - 0.5 * G * tau ** 2), 0
        ball.seg(t_leave, tk, fly)
        contact(tk, "ball1", f"bar{k}", "hit")
        # 小弹跳
        vz = e_bar * G * tf; tc = tk; xc = xl
        for j in range(3):
            tau_f = 2 * vz / G
            def hop(t, tc=tc, xc=xc, vz=vz, zt=ztop):
                tau = t - tc
                return (xc + vx * tau, 0, zt + r1 + vz * tau - 0.5 * G * tau ** 2), 0
            ball.seg(tc, tc + tau_f, hop)
            tc += tau_f; xc += vx * tau_f; vz *= e_bar
            surf = f"bar{k}" if xc < xl + 0.055 else f"tread{k}"
            contact(tc, "ball1", surf, "bounce")
        t_next = tk + TL.BEAT - tf if k < len(TL.STAIRS) - 1 else t_leave_cup
        if k == len(TL.STAIRS) - 1:   # 最后一级踏面缩短：球滚到边缘的时刻正好是飞入铜杯的起飞时刻
            steps[-1]["x1"] = xc + vx * (t_next - tc)
        ball.seg(tc, t_next, lambda t, tc=tc, xc=xc, zt=ztop: ((xc + vx * (t - tc), 0, zt + r1), 0), rolling=True)
        ROLLS.append((tc, t_next, "ball1", "walnut"))
    P["stairs"] = steps
    # ===== ④ 黄铜杯杠杆 =====
    tcup, _ = TL.CUP
    t_leave = t_leave_cup; xe = steps[-1]["x1"]; zlast = Zr - h * 7
    ball.seg(t_leave, tcup, lambda t: ((xe + vx * (t - t_leave), 0, zlast + r1 - 0.5 * G * (t - t_leave) ** 2), 0))
    cup_x = xe + vx * tf7; cup_ball_z = zlast + r1 - hc
    z_cb = cup_ball_z - r1; zL = z_cb - 0.012
    lever = dict(pivot=(cup_x + 0.12, zL), cup_x=cup_x, hook_x=cup_x + 0.24, z=zL, tilt=math.radians(14))
    P["lever"] = lever
    contact(tcup, "ball1", "cup", "hit")
    T["lever"] = tr = Track("lever", "rot")
    t_tip = TL.PEND_RELEASE - tcup
    def lev(t):
        u = (t - tcup) / t_tip
        if u <= 0: return None, 0.0
        if u <= 1: return None, -lever["tilt"] * u * u
        tau = t - TL.PEND_RELEASE   # 撞到限位后的小回弹
        return None, -lever["tilt"] * (1 - 0.06 * math.exp(-tau / 0.05) * abs(math.sin(tau * 60)))
    tr.seg(0, TL.END, lev, extra=[tcup, TL.PEND_RELEASE] + [TL.PEND_RELEASE + j * math.pi / 60 for j in range(1, 5)])
    contact(TL.PEND_RELEASE, "lever", "lever_stop", "hit")
    for j in (1, 2): contact(TL.PEND_RELEASE + j * math.pi / 60, "lever", "lever_stop", "bounce")
    def ball_in_cup(t):   # 钢珠在杯中：随杠杆转动
        ang = lev(t)[1]; px, pz = lever["pivot"]
        dx, dz = cup_x - px, (cup_ball_z) - pz
        c, s = math.cos(ang), math.sin(ang)
        # 绕 y 轴转 ang：x' = x c + z s, z' = -x s + z c
        bounce = 0.0
        tau = t - tcup
        if 0 < tau < 0.07: bounce = 0.0035 * math.sin(math.pi * tau / 0.07)
        # v2：带着 0.5 m/s 的水平速度进杯，撞杯壁后来回滚动，振幅受杯壁限制，0.3 s 衰减
        if tau > 0: dx += min(0.006, 0.4 * vx / (2 * math.pi * 3)) * math.sin(2 * math.pi * 3 * tau) * math.exp(-tau / 0.3)
        return (px + dx * c + dz * s, 0, pz - dx * s + dz * c + bounce), 0
    ball.seg(tcup, TL.END, ball_in_cup)
    contact(tcup + 0.07, "ball1", "cup", "bounce")
    # ===== ⑤ 一米摆锤 =====
    phi0 = -math.radians(40)
    L = solve_L(phi0, TL.PEND_HIT - TL.PEND_RELEASE)
    hold = (lever["hook_x"], zL - 0.03)
    xp = hold[0] + L * math.sin(-phi0); zc = hold[1] - L * (1 - math.cos(phi0)); zpiv = zc + L
    zD = zc - 0.030
    head_r = 0.016
    P["pendulum"] = dict(L=L, pivot=(xp, zpiv), zc=zc, head_r=head_r, phi0=phi0)
    P["zD"] = zD
    f_down = pend_curve(L, phi0, 0.6)
    tq, wq = pend_quarter(L, phi0)
    # 撞止挡后的回弹：恢复系数 0.3，之后每次回到竖直再撞一次
    rebounds = []; w = abs(wq) * 0.3; tt = TL.PEND_HIT
    for i in range(4):
        amp = 2 * math.asin(min(1, w / (2 * math.sqrt(G / L))))
        half = 2 * pend_quarter(L, -max(amp, 1e-4))[0]
        rebounds.append((tt, half, amp)); tt += half; w *= 0.3
    def pend(t):
        if t <= TL.PEND_RELEASE: return None, -phi0
        if t <= TL.PEND_HIT: return None, -f_down(t - TL.PEND_RELEASE)
        for (t0, half, amp) in rebounds:
            if t0 <= t < t0 + half:
                return None, amp * math.sin(math.pi * (t - t0) / half)   # 回摆到左侧（-φ => +roty）
        return None, 0.0
    T["pendulum"] = tr = Track("pendulum", "rot")
    tr.seg(0, TL.END, pend, extra=[TL.PEND_RELEASE, TL.PEND_HIT] + [r[0] for r in rebounds])
    contact(TL.PEND_HIT, "pendulum", "dom0", "hit")
    contact(TL.PEND_HIT, "pendulum", "pend_stop", "hit")
    for (t0, half, amp) in rebounds[1:]:
        contact(t0, "pendulum", "pend_stop", "hit")
    P["head_fn"] = lambda t: (xp + L * math.sin(-pend(t)[1]), zpiv - L * math.cos(pend(t)[1]))
    # ===== ⑥ 骨牌（Bullet）=====
    sim = load_sim()
    P["dominoes"] = domino_spec(xp + head_r - 0.003, zD, sim["meta"]["k"] if sim else None)
    if sim is None:
        P["partial"] = True
        return P, T
    P["sim"] = sim["meta"]
    stage_b(P, T, sim)
    return P, T

def domino_spec(x_first, zD, k=None):
    k = k or 0.6
    n = N_DOMINO; out = []; x = x_first
    for i in range(n):
        hh = 0.04 * 3 ** (i / (n - 1))
        th = hh / 6.0; w = hh / 2.2
        mat = "porcelain" if i < n // 3 else ("maple" if i < 2 * n // 3 else "walnut")
        rho = {"porcelain": 2400, "maple": 700, "walnut": 650}[mat]
        out.append(dict(i=i, x=x, h=hh, t=th, w=w, mat=mat, mass=rho * hh * th * w))
        x += k * hh
    return out

def load_sim():
    p = os.path.join(BUILD, "domino_sim.json")
    if not os.path.exists(p): return None
    meta = json.load(open(p))
    d = np.load(os.path.join(BUILD, "domino_sim.npz"))
    return dict(meta=meta, t=d["t"], loc=d["loc"], quat=d["quat"])

def stage_b(P, T, sim):
    meta = sim["meta"]; zD = P["zD"]
    for c in meta["contacts"]:
        contact(c["t"], c["a"], c["b"], "hit")
    t_land = meta["block_land"]
    blk = meta["block_pivot_x"]
    # ===== ⑦ 牛顿摆 =====
    rc = 0.015; hc = 0.11
    th15 = math.radians(15)
    Lc = solve_L(-th15, TL.BEAT / 2)            # 释放到碰撞 = 1/4 周期 = 半拍
    w_c = math.pi / (2 * pend_quarter(Lc, -th15)[0])   # 近似角频率（小角近似用于后续摆动）
    c1 = blk + 0.17
    xs = [c1 + j * (2 * rc + 0.0003) for j in range(5)]
    top = zD + hc + Lc
    P["cradle"] = dict(xs=xs, rc=rc, L=Lc, top=top, zc=zD + hc, plate=(blk + 0.085, blk + 0.135))
    t_rel = t_land                               # 扳机板被砸下的同一时刻松开挂钩
    t_c0 = t_rel + TL.BEAT / 2
    f1 = pend_curve(Lc, -th15, 0.3)
    w_hit = abs(pend_quarter(Lc, -th15)[1]) * 0.985
    # 后续：两端球交替摆出，每次碰撞损失约 7% 能量
    M = 7850 * 4 / 3 * math.pi * rc ** 3; rm = 0.008; m = 2500 * 4 / 3 * math.pi * rm ** 3
    P["masses"] = dict(cradle=M, marble=m)
    # 小角近似的简谐摆动（15° 时周期误差 < 0.5%），两端球交替摆出，每次碰撞损失约 7% 能量
    amp = w_hit / w_c
    phi_hit = math.asin(0.03 / Lc)            # 右端球摆到 3 cm 处撞到玻璃珠
    swings = []                                # [t0, t1, side, amp, (tau_hit, amp2, psi) or None]
    t0 = t_c0; side = 1; first = True
    while t0 < TL.END + 1:
        if first:
            tau_hit = math.asin(phi_hit / amp) / w_c
            v5 = Lc * amp * w_c * math.cos(w_c * tau_hit)
            e = 0.95
            vm = (1 + e) * M / (M + m) * v5
            v5b = (M - e * m) / (M + m) * v5
            amp2 = math.hypot(phi_hit, v5b / Lc / w_c); psi = math.atan2(phi_hit * w_c, v5b / Lc)
            t1 = t0 + tau_hit + (math.pi - psi) / w_c
            swings.append([t0, t1, side, amp, (tau_hit, amp2, psi)])
            marble_t = t0 + tau_hit; amp = amp2 * math.sqrt(0.93); first = False
        else:
            t1 = t0 + math.pi / w_c
            swings.append([t0, t1, side, amp, None]); amp *= math.sqrt(0.93)
        t0 = t1; side = -side
    def ball_angle(j, t):
        if t < t_rel: return -th15 if j == 0 else 0.0
        if t < t_c0: return f1(t - t_rel) if j == 0 else 0.0
        for (s0, s1, side, A, hit) in swings:
            if s0 <= t < s1:
                if not ((side == 1 and j == 4) or (side == -1 and j == 0)): return 0.0
                tau = t - s0
                if hit is None: return side * A * math.sin(w_c * tau)
                tau_hit, A2, psi = hit
                if tau < tau_hit: return A * math.sin(w_c * tau)
                return A2 * math.sin(psi + w_c * (tau - tau_hit))
        return 0.0
    for j in range(5):
        trk = Track(f"cradle{j}", "rot"); T[f"cradle{j}"] = trk
        ex = [t_rel, t_c0] + [s_[0] for s_ in swings] + [marble_t]
        trk.seg(0, TL.END, lambda t, j=j: (None, -ball_angle(j, t)), extra=ex)
    for (s0, s1, side, A, hit) in swings:
        if s0 < TL.END: contact(s0, "cradle0" if side == 1 else "cradle4", "cradle1" if side == 1 else "cradle3", "hit")
    T["cradle_hook"] = tr = Track("cradle_hook", "rot")
    tr.seg(0, TL.END, lambda t: (None, math.radians(60) * smooth((t - t_rel) / 0.05)), extra=[t_rel])
    T["cradle_plate"] = tr = Track("cradle_plate", "rot")
    tr.seg(0, TL.END, lambda t: (None, math.radians(4) * (1 - (1 - min(1.0, max(0.0, (t - t_rel) / 0.03))) ** 2)), extra=[t_rel, t_rel + 0.03])   # 被木块砸下：起始速度最大，压到底停住
    # ===== ⑧ 玻璃管滚道 =====
    r_m = rm; P["r_marble"] = r_m
    zc5 = zD + hc + Lc * (1 - math.cos(phi_hit))
    xm0 = xs[4] + 0.03 + rc + r_m
    v_g = 5 / 7 * vm
    ma = Track("marble0", "loc", r_m); T["marble0"] = ma
    ma.seg(0, marble_t, lambda t: ((xm0, 0, zc5), 0))
    contact(marble_t, "cradle4", "marble0", "hit")
    # 先滑后滚：0.05 s 内从 vm 平滑过渡到 v_g
    def gpos(t):
        tau = t - marble_t; ts_ = 0.05
        if tau < ts_: s = vm * tau - (vm - v_g) * tau ** 2 / (2 * ts_)
        else: s = vm * ts_ - (vm - v_g) * ts_ / 2 + v_g * (tau - ts_)
        return s
    taps = []
    for (tg, note) in TL.GLASS:
        taps.append(dict(x=xm0 + gpos(tg), note=note, t=tg))
        contact(tg, "marble0", f"gtube{len(taps)-1}", "hit")
    hf = (1.127 + 0.0) ** 2   # 占位，下面重算
    e_c = 0.85; Tb = TL.BEAT / 2
    vz_ss = (G * Tb / 2) * 2 * e_c / (1 + e_c)          # 稳态弹起速度
    vz_in = vz_ss / e_c; hf = vz_in ** 2 / (2 * G); tfall = vz_in / G
    t_end_g = TL.BOWLS0 - tfall
    x_end_g = xm0 + gpos(t_end_g)
    TH_G = 0.022; tap_t = [tp["t"] for tp in taps]
    ma.seg(marble_t, t_end_g, lambda t: ((xm0 + gpos(t), 0, zc5 + microhop(t, tap_t, TH_G)), 0), rolling=True,
           extra=tap_t + [x + TH_G for x in tap_t])
    for k, x in enumerate(tap_t): contact(x + TH_G, "marble0", "grail1", "bounce")
    P["glass_hop"] = TH_G
    ROLLS.append((marble_t, t_end_g, "marble0", "glass"))
    P["glass"] = dict(x0=xm0 - 0.03, x1=x_end_g, z=zc5 - r_m, taps=taps, v=v_g)
    # ===== ⑨ 陶瓷碗：稳态弹跳，每八分音符一次 =====
    vx = v_g
    ma.seg(t_end_g, TL.BOWLS0, lambda t: ((x_end_g + vx * (t - t_end_g), 0, zc5 - 0.5 * G * (t - t_end_g) ** 2), 0))
    bowls = []; xb = x_end_g + vx * tfall; zb = zc5 - hf; tb_ = TL.BOWLS0
    for k, note in enumerate(TL.BOWL_NOTES + ["PAN"]):
        if note == "PAN":
            break
        bowls.append(dict(x=xb, ztop=zb - r_m, note=note, t=tb_))
        contact(tb_, "marble0", f"bowl{k}", "hit")
        def hop(t, tb_=tb_, xb=xb, zb=zb):
            tau = t - tb_
            return (xb + vx * tau, 0, zb + vz_ss * tau - 0.5 * G * tau ** 2), 0
        ma.seg(tb_, tb_ + Tb, hop)
        xb += vx * Tb; zb += vz_ss * Tb - 0.5 * G * Tb ** 2; tb_ += Tb
    P["bowls"] = bowls
    # ===== ⑩ 天平 =====
    tpan, _ = TL.PAN
    pan_x, pan_z = xb, zb - r_m
    bal = dict(pan_x=pan_x, pan_z=pan_z, pivot_x=pan_x + 0.14, arm=0.14, tilt=math.radians(10))
    pz_top = pan_z + 0.16
    bal["pivot_z"] = pz_top
    P["balance"] = bal
    contact(tpan, "marble0", "pan", "hit")
    t_release_w = TL.WEIGHT_TAUT - math.sqrt(2 * 0.07 / G)
    # v2：珠子砸进托盘的冲量先让横梁快速下沉一点，再由油阻尼筒拖住（过阻尼：快升慢落），然后才是慢慢的配重侧倾
    th_imp = math.radians(3.0)
    def beam(t):
        u = (t - tpan - 0.05) / (t_release_w - tpan - 0.05)
        base = -bal["tilt"] * smooth(u) if u < 1 else -bal["tilt"]   # 左端下沉（-roty）
        tau = t - tpan
        imp = -th_imp * (math.exp(-tau / 0.6) - math.exp(-tau / 0.04)) / 0.86 if tau > 0 else 0.0
        return None, base + imp
    T["beam"] = tr = Track("beam", "rot"); tr.seg(0, TL.END, beam, extra=[tpan, t_release_w])
    def pan_drop(t):
        ang = beam(t)[1]
        return bal["arm"] * math.sin(-ang)
    # v2：托盘是曲率半径 Rc 的浅碟。珠子带着水平速度进盘，先小跳一下，然后在碟里来回滚动（滚动摆：ω = √(5g / 7(Rc−r))），
    # 振幅按滚动摩擦与油阻尼指数衰减；托盘挂在三根线上，被砸时先下沉再回弹（≈5 Hz，迅速衰减）
    Rc = 0.06; rp = Rc - r_m; om_p = math.sqrt(5 * G / (7 * rp))
    ks = sorted(k for k in ma.s if k < tpan)[-2:]
    vin_x = (ma.s[ks[1]][0][0] - ma.s[ks[0]][0][0]) / (ks[1] - ks[0])
    vh = 0.6 * vin_x; A_p = vh / om_p; td_p = 0.9; th_hop = 0.08
    bal.update(Rc=Rc, A=A_p, omega=om_p)
    def pan_bounce(t):
        tau = t - tpan
        return -0.004 * math.exp(-tau / 0.12) * math.sin(2 * math.pi * 5 * tau) if tau > 0 else 0.0
    def mpan(t):
        tau = t - tpan
        xr = A_p * math.sin(om_p * tau) * math.exp(-tau / td_p)
        zr = xr * xr / (2 * rp)
        b = (G * th_hop / 2) * tau - 0.5 * G * tau * tau if 0 < tau < th_hop else 0.0
        return (pan_x + xr, 0, pan_z + r_m + zr - pan_drop(t) + pan_bounce(t) + b), 0
    ma.seg(tpan, TL.END, mpan, extra=[tpan + th_hop])
    contact(tpan + th_hop, "marble0", "pan", "bounce")
    ROLLS.append((tpan + th_hop, tpan + 4.0, "marble0", "pan_l"))
    T["pan_l"] = tr = Track("pan_l", "loc")
    tr.seg(0, TL.END, lambda t: ((pan_x, 0, pan_z - pan_drop(t) + pan_bounce(t)), 0), extra=[tpan])
    T["pan_r"] = tr = Track("pan_r", "loc")
    tr.seg(0, TL.END, lambda t: ((pan_x + 2 * bal["arm"], 0, pan_z + pan_drop(t)), 0))
    # ===== ⑪ 铸铁配重 + 调速风扇 + 星轮分珠器 =====
    xw = pan_x + 0.44
    w_top = 0.80; v_w = 0.04
    t_floor = TL.WEIGHT_TAUT + (w_top - 0.07 - 0.12) / v_w
    def wpos(t):
        if t < t_release_w: z = w_top
        elif t < TL.WEIGHT_TAUT: z = w_top - 0.5 * G * (t - t_release_w) ** 2
        elif t < t_floor:
            tau = t - TL.WEIGHT_TAUT; om_r = 2 * math.pi * 8
            z = w_top - 0.07 - v_w * tau - 0.5 * (G * (TL.WEIGHT_TAUT - t_release_w) - v_w) / om_r * math.exp(-tau / 0.12) * math.sin(om_r * tau)
        else: z = 0.12
        return (xw, 0.06, z), 0
    T["weight"] = tr = Track("weight", "loc"); tr.seg(0, TL.END, wpos, extra=[t_release_w, TL.WEIGHT_TAUT, t_floor])
    contact(TL.WEIGHT_TAUT, "weight", "rope", "jerk"); contact(t_floor, "weight", "felt", "hit")
    T["latch_pin"] = tr = Track("latch_pin", "loc")
    tr.seg(0, TL.END, lambda t: ((xw + 0.05 * smooth((t - t_release_w + 0.08) / 0.08), 0.06, w_top + 0.05), 0), extra=[t_release_w])
    xd = xw + 0.16; zd = 0.62
    wheel_w = (math.pi / 3) / TL.BEAT
    def wheel(t):   # v3：顺时针（从镜头看），齿槽从上方转到右侧放珠
        if t < TL.WEIGHT_TAUT: return None, 0.0
        return None, wheel_w * (min(t, t_floor) - TL.WEIGHT_TAUT)
    T["star"] = tr = Track("star", "rot"); tr.seg(0, TL.END, wheel)
    T["fan"] = tr = Track("fan", "rot")
    def fan(t):   # v2：起转（0.15 s）和停转（0.6 s）都带惯性
        if t < TL.WEIGHT_TAUT: return None, 0.0
        w14 = wheel_w * 14; tau = min(t, t_floor) - TL.WEIGHT_TAUT
        a = w14 * (tau - 0.15 * (1 - math.exp(-tau / 0.15)))
        if t > t_floor: a += w14 * 0.6 * (1 - math.exp(-(t - t_floor) / 0.6))
        return None, -a
    tr.seg(0, TL.END, fan)
    ROLLS.append((TL.WEIGHT_TAUT, min(TL.END, t_floor + 1.5), "fan", "air"))
    P["weight"] = dict(x=xw, top=w_top, floor=0.12, pulley_z=1.02)
    P["dispenser"] = dict(x=xd, z=zd)
    # ===== ⑫ 水瓶琴：5 颗珠走同一条轨道 =====
    a_t = 1.5; t_a = 0.3; v_b = a_t * t_a
    s_a = 0.5 * a_t * t_a ** 2
    def sb(tau): return 0.5 * a_t * tau ** 2 if tau < t_a else s_a + v_b * (tau - t_a)
    track_z0 = zd - 0.06
    slope_b = math.radians(1.2)
    def bpos(tau):
        s = sb(tau)
        if s <= s_a: dz = -s * math.tan(math.asin(a_t * 1.4 / G))
        else: dz = -s_a * math.tan(math.asin(a_t * 1.4 / G)) - (s - s_a) * math.tan(slope_b)
        return xd + s, track_z0 + r_m + dz
    bottles = []
    for k, note in enumerate(TL.BOTTLE_PATH):
        tau = (k + 1) * TL.BEAT; x_, z_ = bpos(tau)
        bottles.append(dict(x=x_, zc=z_, note=note))
    s_end = sb(TL.BEAT * 8) + 0.10
    tau_end = t_a + (s_end - s_a) / v_b
    x_end, z_end = bpos(tau_end)
    P["bottles"] = dict(list=bottles, x0=xd, x1=x_end, z0=track_z0, s_a=s_a, slope=slope_b, a_slope=math.asin(a_t * 1.4 / G))
    # ===== ⑬ 钢管风铃井 =====
    chimes = []; p = np.array([x_end, 0.0, z_end]); v = np.array([v_b, 0.0, 0.0]); tt = 0.0
    path = []   # (tau0, tau1, p0, v0)
    gaps = [0.07, 0.08, 0.075, 0.07]
    for k, note in enumerate(TL.CHIME_NOTES):
        # 求下落 gaps[k] 所需时间
        a_, b_, c_ = 0.5 * G, -v[2], -gaps[k]
        dt = (-b_ + math.sqrt(b_ * b_ - 4 * a_ * c_)) / (2 * a_)
        path.append((tt, tt + dt, p.copy(), v.copy()))
        p = p + v * dt + np.array([0, 0, -0.5 * G * dt * dt]); v = v + np.array([0, 0, -G * dt]); tt += dt
        vin = v.copy()
        v = np.array([-0.55 * v[0] if k == 0 else -0.6 * v[0], 0, 0.72 * v[2]])
        if k == 0: v[0] = -0.35
        dv = v - vin; n = dv / np.linalg.norm(dv)
        rt = 0.011
        chimes.append(dict(c=(p - n * (r_m + rt)).tolist(), note=note, tau=tt))
    cup_z = 0.16
    a_, b_, c_ = 0.5 * G, -v[2], -(p[2] - (cup_z + r_m))
    dt = (-b_ + math.sqrt(b_ * b_ - 4 * a_ * c_)) / (2 * a_)
    path.append((tt, tt + dt, p.copy(), v.copy()))
    p_cup = p + v * dt + np.array([0, 0, -0.5 * G * dt * dt]); tau_cup = tt + dt
    P["chimes"] = chimes
    P["tcup"] = dict(x=float(p_cup[0]), z=cup_z)
    # v3 星轮几何：齿槽中心半径 R，初始齿槽角 th0 由"落轨点 = 轨道 s=R 处、且与 v2 的水瓶节拍一致"反算
    R_star = 0.035; w_deg_ = 60.0 / TL.BEAT; v_tan_ = math.radians(w_deg_) * R_star
    tau_land_ = math.sqrt(2 * R_star / a_t); zl_ = bpos(tau_land_)[1]
    tf_ = (-v_tan_ + math.sqrt(v_tan_ ** 2 + 2 * G * (zd - zl_))) / G
    STAR = dict(R=R_star, th0=(tau_land_ - tf_) * w_deg_)
    P["dispenser"].update(star_R=R_star, th0=STAR["th0"])
    # 5 颗珠
    land_times = []
    for mi in range(TL.MARBLES):
        name = f"m{mi+1}"; trk = Track(name, "loc", r_m); T[name] = trk
        t0 = TL.WEIGHT_TAUT + mi * TL.BEAT
        stack = (xd, 0, zd + 0.11 + mi * 2 * r_m * 1.02)
        z_exit = zd + 0.06; H_drop = z_exit - (track_z0 + r_m)
        td = math.sqrt(2 * H_drop / G)     # 从星轮口自由落体到轨道起点
        # v3：星轮真正"一格放一颗"。配重绳绷紧（24.0 s）星轮才开始顺时针转（60°/拍）。
        # 珠子在星轮右侧的齿槽里被护板挡住，齿槽转到 0°（正右方）离开护板才落到轨道上；料管底部的珠子在齿槽转到 90°（正上方）时落进齿槽。
        # 初始齿槽角 th0 反算得到：落轨点正好是轨道上 s=R_STAR 处，此后过每只水瓶的时刻（音符）与 v2 完全一致。
        R_ST = STAR["R"]; th0 = STAR["th0"]; w_deg = 60.0 / TL.BEAT
        def pocket(k, t):   # 第 k 颗珠所在齿槽的角度（度）
            return th0 + 60 * k - w_deg * max(0.0, t - TL.WEIGHT_TAUT)
        rel_k = TL.WEIGHT_TAUT + (th0 + 60 * mi) / w_deg            # 齿槽转到 0°：离开护板
        load_k = TL.WEIGHT_TAUT + (th0 + 60 * mi - 90) / w_deg       # 齿槽转到 90°：从料管落进齿槽（前两颗预先装好）
        z_top = zd + R_ST + r_m                                       # 料管最下面一颗珠的位置（压在星轮顶上）
        loads = [TL.WEIGHT_TAUT + (th0 + 60 * j - 90) / w_deg for j in range(TL.MARBLES)]
        def mpos(t, mi=mi, rel_k=rel_k, load_k=load_k, loads=loads):
            if mi >= 2 and t < load_k:
                below = sum(1 for j in range(2, mi) if t >= loads[j])
                dz = sum(min(2 * r_m * 1.02, 0.5 * G * (t - loads[j]) ** 2) for j in range(2, mi) if t >= loads[j])
                return (xd, 0, z_top + (mi - 2) * 2 * r_m * 1.02 - dz), 0
            a = math.radians(pocket(mi, t)); pz = zd + (R_ST - 0.001) * math.sin(a); px = xd + (R_ST - 0.001) * math.cos(a)
            if mi >= 2 and t < load_k + 0.04:      # 落进齿槽的 0.04 s 过渡（约 8 mm）
                u = (t - load_k) / 0.04
                return (lerp_(xd, px, u), 0, lerp_(z_top, pz, u)), 0
            return (px, 0, pz), 0
        def lerp_(a, b, u): return a + (b - a) * u
        tl0 = rel_k
        s_land = R_ST; tau_land = math.sqrt(2 * s_land / a_t); tl1 = t0 + tau_land; xl, zl = bpos(tau_land)
        v_tan = math.radians(w_deg) * R_ST; td = tl1 - tl0
        ex = [x for x in loads[2:mi + 1]] + [x + 0.04 for x in loads[2:mi + 1]] + [TL.WEIGHT_TAUT]
        trk.seg(0, tl0, mpos, extra=ex + list(np.linspace(TL.WEIGHT_TAUT, tl0, 20)))
        z_rel = zd; x_rel = xd + R_ST - 0.001
        trk.seg(tl0, tl1, lambda t, tl0=tl0, td=td, x_rel=x_rel, xl=xl, zl=zl: ((x_rel + (xl - x_rel) * (t - tl0) / td, 0,
                z_rel - v_tan * (t - tl0) - 0.5 * G * (t - tl0) ** 2 + (zl - (z_rel - v_tan * td - 0.5 * G * td * td)) * (t - tl0) / td), 0))
        if mi == 0: print("STAR release %.3f land %.3f fall %.3f s (free-fall would be %.3f)" % (tl0, tl1, td, (-v_tan + math.sqrt(v_tan ** 2 + 2 * G * (z_rel - zl))) / G))
        contact(tl1, name, "track", "hit")
        bt_ = [t0 + (k + 1) * TL.BEAT for k in range(8)]; TH_B = 0.018
        trk.seg(tl1, t0 + tau_end, lambda t, t0=t0, bt_=bt_: ((bpos(t - t0)[0], 0, bpos(t - t0)[1] + microhop(t, bt_, TH_B)), 0), rolling=True,
                extra=bt_ + [x + TH_B for x in bt_])
        for x in bt_: contact(x + TH_B, name, "btrack1", "bounce")
        ROLLS.append((tl1, t0 + tau_end, name, "brass"))
        for k in range(8): contact(t0 + (k + 1) * TL.BEAT, name, f"bottle{k}", "hit")
        # 最后一段：落到杯里已有珠子之上 / 已下沉的杯底（每颗先到的珠使杯下沉 4 mm）
        lift_m = [0, 0, 0, 0, 2 * r_m * 0.8][mi]
        a0l, _, p0l, v0l = path[-1]
        zt = cup_z + r_m + lift_m - 0.004 * mi
        a_, b_, c_ = 0.5 * G, -v0l[2], -(p0l[2] - zt)
        dtl = (-b_ + math.sqrt(b_ * b_ - 4 * a_ * c_)) / (2 * a_)
        path_m = path[:-1] + [(a0l, a0l + dtl, p0l, v0l)]
        for (a0, a1, p0, v0) in path_m:
            def fl(t, a0=a0, p0=p0, v0=v0, t0=t0):
                tau = t - t0 - tau_end - a0
                q = p0 + v0 * tau + np.array([0, 0, -0.5 * G * tau * tau]); return tuple(q), 0
            trk.seg(t0 + tau_end + a0, t0 + tau_end + a1, fl)
        for k, ch in enumerate(chimes): contact(t0 + tau_end + ch["tau"], name, f"chime{k}", "hit")
        tl_ = t0 + tau_end + a0l + dtl; land_times.append(tl_)
        T[name + "_landx"] = float(p0l[0] + v0l[0] * dtl)
        contact(tl_, name, "tcup", "hit")
        # 落入杯中：在杯中按顺序堆放（小弹跳后静止），随杯下沉
        T[name + "_land"] = (tl_, mi)
    # ===== ⑭ 弹射 =====
    t_last = land_times[-1]
    t_trip = TL.LAUNCH - 0.087
    t_fd = math.sqrt(2 * 0.004 / G); t_rel_c = t_trip - t_fd
    def cup_sink(t):
        if t < land_times[0]: return 0.0
        n = sum(1 for x in land_times if t >= x)
        base = sum(0.004 * (1 - math.exp(-(t - x) / 0.025) * math.cos(2 * math.pi * 12 * (t - x))) for x in land_times if t >= x)
        if t >= t_last:
            u = min(1.0, (t - t_last) / (t_rel_c - t_last)); base += 0.022 * u ** 1.5
            if t > t_rel_c: tau = min(t, t_trip) - t_rel_c; base += 0.5 * G * tau * tau
        return base
    for mi in range(TL.MARBLES):
        name = f"m{mi+1}"; trk = T[name]; tl_, _ = T.pop(name + "_land")
        off = [(-0.009, -0.009), (0.009, -0.009), (-0.009, 0.009), (0.009, 0.009), (0, 0)][mi]
        lift = [0, 0, 0, 0, 2 * r_m * 0.8][mi]
        lx_ = T.pop(name + "_landx")
        def incup(t, tl_=tl_, off=off, lift=lift, lx_=lx_):
            tau = t - tl_; b = 0.004 * math.sin(math.pi * tau / 0.06) if tau < 0.06 else 0
            u = smooth(tau / 0.08)            # 落入杯中后滚到自己的位置
            return (lx_ + (P["tcup"]["x"] + off[0] - lx_) * u, off[1] * u, cup_z + r_m + lift - cup_sink(t) + b), 0
        trk.seg(tl_, TL.END, incup, extra=land_times + [t_rel_c, t_trip])
    T["tcup"] = tr = Track("tcup", "loc")
    tr.seg(0, TL.END, lambda t: ((P["tcup"]["x"], 0, cup_z - cup_sink(t)), 0), extra=land_times + [t_rel_c, t_trip])
    contact(t_trip, "tcup", "trigger", "click")
    # 弹射臂
    R = 0.2; a0 = math.radians(215); a1 = math.radians(160)
    piv = (P["tcup"]["x"] + 0.42, 0.13)
    launch = (piv[0] + R * math.cos(a1), piv[1] + R * math.sin(a1))
    T_air = TL.LAND - TL.LAUNCH
    P["catapult"] = dict(pivot=piv, R=R, a0=a0, a1=a1)
    # 落点（接球槽）高度由漏斗决定：漏斗底 -> 落到扳机 0.12 m；扳机板上表面 0.04
    r_b = 0.015; P["r_brass"] = r_b
    trig_z = 0.05; k_f = 0.0075; R0 = 0.25; r_h = 0.03
    depth = k_f * (1 / r_h - 1 / R0)
    z_exit = trig_z + r_b + 0.12
    z_rim = z_exit + depth
    land_pt = (None, z_rim + 0.02)
    dz = land_pt[1] - launch[1]
    vz0 = (dz + 0.5 * G * T_air ** 2) / T_air
    vx0 = vz0 / math.tan(math.radians(70))
    land_x = launch[0] + vx0 * T_air
    xf = land_x + 0.10
    vl = math.hypot(vx0, vz0); om = vl / R
    t_s = 2 * (a0 - a1) / om
    t_trip = TL.LAUNCH - t_s
    def arm(t):
        if t < t_trip: return None, -a0
        if t < TL.LAUNCH:
            tau = t - t_trip; return None, -(a0 - 0.5 * (om / t_s) * tau ** 2)
        tau = t - TL.LAUNCH
        return None, -(a1 + math.radians(6) * math.exp(-tau / 0.12) * abs(math.sin(tau * 40)))
    reb = [TL.LAUNCH + j * math.pi / 40 for j in range(1, 7)]
    T["arm"] = tr = Track("arm", "rot"); tr.seg(0, TL.END, arm, extra=[t_trip, TL.LAUNCH] + reb)
    contact(TL.LAUNCH, "arm", "arm_stop", "hit")
    for x in reb[:3]: contact(x, "arm", "arm_stop", "bounce")
    bb = Track("ball2", "loc", r_b); T["ball2"] = bb
    def onarm(t):   # 铜球坐在勺里：勺口法线 n = (sin a, 0, -cos a)
        ang = -arm(t)[1]; off = r_b + 0.004
        return (piv[0] + R * math.cos(ang) + off * math.sin(ang), 0, piv[1] + R * math.sin(ang) - off * math.cos(ang)), 0
    bb.seg(0, TL.LAUNCH, onarm, extra=[t_trip])
    p_l = onarm(TL.LAUNCH)[0]
    bb.seg(TL.LAUNCH, TL.LAND, lambda t: ((p_l[0] + vx0 * (t - TL.LAUNCH), 0, p_l[2] + vz0 * (t - TL.LAUNCH) - 0.5 * G * (t - TL.LAUNCH) ** 2), 0))
    p_land = (p_l[0] + vx0 * T_air, 0, p_l[2] + vz0 * T_air - 0.5 * G * T_air ** 2)
    contact(TL.LAND, "ball2", "chute", "hit")
    # ===== ⑮ 接球槽 + 漏斗 =====
    xf = p_land[0] + 0.10
    cen = (xf, R0)
    v0 = math.sqrt(G * k_f / R0)
    p_in = (xf, 0.0, z_rim + r_b)
    # 接球槽：0.25 s 从落点平滑滑到漏斗边缘前缘
    def chute(t):
        u = (t - TL.LAND) / (TL.FUNNEL_IN - TL.LAND)
        uu = u - (1 - v0 * (TL.FUNNEL_IN - TL.LAND) / max(1e-6, (p_in[0] - p_land[0]))) * 0  # 线性
        s = 1 - (1 - u) ** 2 * 0.0
        x = p_land[0] + (p_in[0] - p_land[0]) * (2 * u - u * u) if u < 1 else p_in[0]
        z = p_land[2] + (p_in[2] - p_land[2]) * smooth(u)
        return (x, 0, z), 0
    bb.seg(TL.LAND, TL.FUNNEL_IN, chute, rolling=True)
    ROLLS.append((TL.LAND, TL.FUNNEL_IN, "ball2", "copper"))
    t_exit = TL.TRIGGER - math.sqrt(2 * 0.12 / G)
    D = t_exit - TL.FUNNEL_IN
    def rr(u): return r_h + (R0 - r_h) * (1 - u ** 1.7) ** 1.25
    us = np.linspace(0, 1, 4000); rs = np.array([rr(u) for u in us])
    om_s = np.sqrt(G * k_f) / rs ** 1.5
    ang = np.concatenate([[0], np.cumsum((om_s[1:] + om_s[:-1]) / 2 * np.diff(us) * D)])
    def fun(t):
        u = (t - TL.FUNNEL_IN) / D
        r_ = float(np.interp(u, us, rs)); a_ = float(np.interp(u, us, ang))
        th_ = -math.pi / 2 + a_
        z = z_rim - k_f * (1 / r_ - 1 / R0) + r_b
        return (cen[0] + r_ * math.cos(th_), cen[1] + r_ * math.sin(th_), z), 0
    bb.seg(TL.FUNNEL_IN, t_exit, fun, rolling=True, extra=list(np.linspace(TL.FUNNEL_IN, t_exit, 3000)))
    ROLLS.append((TL.FUNNEL_IN, t_exit, "ball2", "funnel"))
    P["funnel"] = dict(c=cen, R0=R0, r_h=r_h, k=k_f, z_rim=z_rim, depth=depth, revs=float(ang[-1] / (2 * math.pi)))
    p_ex = fun(t_exit)[0]
    bb.seg(t_exit, TL.TRIGGER, lambda t: ((p_ex[0], p_ex[1], p_ex[2] - 0.5 * G * (t - t_exit) ** 2), 0))
    contact(TL.TRIGGER, "ball2", "trigger2", "hit"); contact(TL.TRIGGER + 0.08, "ball2", "trigger2", "bounce")
    # ===== ⑯ 摆锤敲钟 =====
    tb, _ = TL.BELL
    phh = -math.radians(60)
    Lh = solve_L(phh, tb - TL.TRIGGER)
    bell_x = xf + 0.55; bell_c = (bell_x, R0); bell_R = 0.11; bell_zc = 0.42
    head_rh = 0.022
    hp = (bell_x - bell_R - head_rh - 0.002, bell_zc + Lh)
    P["bell"] = dict(x=bell_x, y=R0, R=bell_R, zc=bell_zc, hammer_pivot=hp, Lh=Lh, head_r=head_rh)
    fh = pend_curve(Lh, phh, 0.4)
    def ham(t):
        if t < TL.TRIGGER: return None, -phh
        if t < tb: return None, -fh(t - TL.TRIGGER)
        tau = t - tb
        return None, math.radians(9) * math.sin(math.pi * min(tau, 0.42) / 0.42) * math.exp(-tau / 0.8) if tau < 0.42 else 0.0
    T["hammer"] = tr = Track("hammer", "rot"); tr.seg(0, TL.END, ham, extra=[TL.TRIGGER, tb, tb + 0.42])
    contact(tb, "hammer", "bell", "hit"); contact(tb + 0.42, "hammer", "hammer_stop", "hit")
    T["bell"] = tr = Track("bell", "rot")
    tr.seg(0, TL.END, lambda t: (None, 0 if t < tb else -math.radians(1.2) * math.sin(2 * math.pi * (t - tb) / 1.1) * math.exp(-(t - tb) / 2.5)))
    T["trigger2"] = tr = Track("trigger2", "rot")
    tr.seg(0, TL.END, lambda t: (None, math.radians(8) * smooth((t - TL.TRIGGER) / 0.04)), extra=[TL.TRIGGER])
    # ===== ⑰ 收尾 =====
    tce, _ = TL.CUP_END
    p_t = (p_ex[0], p_ex[1], trig_z + r_b)
    # v3（J："全片最后一个碗"放低）：木杯嵌进台面 3.2 cm，杯沿低于跑道面 1.2 cm；
    # 钢球以 0.38 m/s 滚出跑道末端、平抛落进杯底（离杯沿最小间隙约 4 mm，不穿模）
    CUP_SINK = 0.032; floor_top = 0.012 - CUP_SINK
    h_drop = (trig_z + r_b - 0.025) - floor_top; t_f = math.sqrt(2 * h_drop / G)
    ramp_T = 0.35; v1 = 0.55; T_roll = tce - TL.TRIGGER - 0.08 - ramp_T - t_f
    v_end = 0.38; dec = (v1 - v_end) / T_roll
    X_roll = (v1 + v_end) / 2 * T_roll
    def fin(t):
        tau = t - TL.TRIGGER - 0.08
        if tau < 0:   # v2：砸到扳机板后弹起一下（恢复系数约 0.26），不再原地定住
            tt_ = t - TL.TRIGGER
            if tt_ < 0: return p_t, 0
            return (p_t[0], p_t[1], p_t[2] + (G * 0.08 / 2) * tt_ - 0.5 * G * tt_ * tt_), 0
        if tau < ramp_T:
            s = 0.5 * (v1 / ramp_T) * tau ** 2
            return (p_t[0] + s, p_t[1], p_t[2] - 0.025 * smooth(tau / ramp_T)), 0
        s0 = 0.5 * v1 * ramp_T; tau2 = tau - ramp_T
        if tau2 < T_roll:
            s = s0 + v1 * tau2 - 0.5 * dec * tau2 ** 2
            return (p_t[0] + s, p_t[1], p_t[2] - 0.025), 0
        tau3 = tau2 - T_roll; s = s0 + X_roll + v_end * min(tau3, t_f)
        zz = p_t[2] - 0.025 - 0.5 * G * min(tau3, t_f) ** 2
        if tau3 > t_f:   # 落进杯底后小幅来回滚动、衰减到静止（杯内可动范围 ±15 mm，振幅限 12 mm）
            t4 = tau3 - t_f; om_c = 2 * math.pi * 2.2
            s += min(0.012, v_end / om_c) * math.sin(om_c * t4) * math.exp(-t4 / 0.45)
            if t4 < 0.05: zz += (G * 0.05 / 2) * t4 - 0.5 * G * t4 * t4
        return (p_t[0] + s, p_t[1], zz), 0
    bb.seg(TL.TRIGGER, TL.END, fin, rolling=True, extra=[tce])
    ROLLS.append((TL.TRIGGER + 0.08, tce - t_f, "ball2", "walnut"))
    contact(tce, "ball2", "endcup", "hit")
    x_edge = p_t[0] + 0.5 * v1 * ramp_T + X_roll
    P["endcup"] = dict(x=x_edge + 0.036, y=p_t[1], z=p_t[2] - 0.025 - 0.015 - r_b, board_z=p_t[2] - 0.025 - r_b, sink=CUP_SINK, edge_x=x_edge)
    P["trig2"] = dict(x=p_t[0], y=p_t[1], z=trig_z)
    P["length"] = P["endcup"]["x"] + 0.4

def run(write=True):
    P, T = design()
    out = dict(P={k: v for k, v in P.items() if k != "head_fn"}, tracks={k: v.export() for k, v in T.items()},
               contacts=sorted(CONTACTS, key=lambda c: c["t"]), rolls=ROLLS)
    if write:
        os.makedirs(BUILD, exist_ok=True)
        json.dump(out, open(os.path.join(BUILD, "motion.json"), "w"))
    return P, out

if __name__ == "__main__":
    P, out = run()
    print("partial" if P.get("partial") else "full", "tracks:", len(out["tracks"]), "contacts:", len(out["contacts"]))
    print("pendulum L=%.4f pivot=%s zD=%.3f" % (P["pendulum"]["L"], P["pendulum"]["pivot"], P["zD"]))
    print("rail slope %.2f deg" % P["rail"]["slope_deg"])
    if not P.get("partial"):
        print("length %.2f m, funnel revs %.1f" % (P["length"], P["funnel"]["revs"]))
