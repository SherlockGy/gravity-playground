# 重力乐园 · 摄像机（一镜到底）+ 灯光 + 渲染设置。由 build_scene.py exec 执行（共享其变量）
import numpy as np, math
from mathutils import Vector
import blib as _bl

def tpos(name, t):
    tr = TR[name]; ts = tr["t"]; Lx = np.array(tr["loc"])
    return np.array([np.interp(t, ts, Lx[:, i]) for i in range(3)])
# 骨牌波前位置
on = sorted([(c["t"], int(c["b"][3:])) for c in meta["contacts"] if c["b"].startswith("dom")])
wave_t = [TL.PEND_HIT] + [o_[0] for o_ in on]; wave_x = [meta["doms"][0]["x"]] + [meta["doms"][o_[1]]["x"] for o_ in on]
def wave(t): return float(np.interp(t, wave_t, wave_x))
xs_ = P["cradle"]["xs"]; bl = P["balance"]; fu = P["funnel"]; be = P["bell"]; ca = P["catapult"]; pd = P["pendulum"]
def lerp(a, b, u): return a + (b - a) * u
def ss(u): u = min(1, max(0, u)); return u * u * (3 - 2 * u)
def marbles_mean(t):
    xs = [tpos(f"m{i+1}", t)[0] for i in range(5)]
    return float(np.clip(np.mean(xs), P["bottles"]["x0"] + 0.4, P["bottles"]["x1"] - 0.2))
# ================= v2 摄影：11 个镜头、7 处有动机的剪切 =================
# 原则：观众必须看清每一次“因 -> 果”的交接。镜头跟着运动体横移（相对运动小），长焦 + 足够景深，
# 每个触发瞬间前后都有停顿；广角只在平静的拍子出现；动态模糊按镜头单独设置（默认 0.10，只有弹射飞行用 0.35）。
# 每个镜头函数返回 (target, dist, elev°, azim°, lens mm, f-stop, focus_point)；azim=0 为正侧面（相机在 -y）。
def ease(t, t0, t1): return ss((t - t0) / (t1 - t0))
def at(*a): return np.array(a, dtype=float)
st_ = P["stairs"]; lv = P["lever"]; gl_ = P["glass"]; bw_ = P["bowls"]; wt_ = P["weight"]; dp_ = P["dispenser"]
bt_ = P["bottles"]; ch_ = P["chimes"]; tc_ = P["tcup"]; ec_ = P["endcup"]; zD_ = P["zD"]; mt_ = P["metronome"]
def follow(name, t, lead=0.0, zoff=0.0):
    p = tpos(name, t); return at(p[0] + lead, 0.0, p[2] + zoff)
SHOTS = []   # (名称, t0, t1, 函数, 模糊快门, 平滑 sigma s, 说明)
def S(name, t0, t1, shutter, sig, note):
    def deco(f): SHOTS.append((name, t0, t1, f, shutter, sig, note)); return f
    return deco
def cut(t): return (round(t * TL.FPS + 0.5) - 0.5) / TL.FPS     # 剪切点放在两帧正中间，动态模糊不会跨剪切点
C = [0.0, cut(2.40), cut(8.15), cut(8.95), cut(11.55), cut(19.95), cut(23.75), cut(30.80), cut(31.98), cut(33.20), cut(35.72), TL.END]

@S("A 节拍器与放珠机构", C[0], C[1], 0.10, 0.25, "70 mm 固定中近景，节拍器摆杆的整个摆幅、棘轮和起点挡板同时完整入画（v2 的 100 mm 只框住半个摆杆和半个棘轮）；1.4–2.0 s 焦点从摆杆移到挡板与钢珠，观众先看清节拍怎样一格格推动棘轮，再看到钢珠被放出")
def shA(t):
    tg = at(mt_["x"] + 0.14, 0, mt_["z"] + 0.13)   # 机构跨度 x≈-0.37…0.0，z≈1.43…1.68
    fp = lerp(at(mt_["x"], -0.04, mt_["z"] + 0.12), at(0.02, 0, rail["z0"] + 0.015), ease(t, 1.4, 2.0))
    return tg, lerp(1.02, 0.99, t / 2.4), 6, -8, 70, 11, fp

@S("B 滚轨与红木台阶横移", C[1], C[2], 0.12, 0.45, "60 mm 正侧面，镜头与钢珠同速横移，台阶一级级在画面中央被砸响；钢珠进铜杯前减速停稳，停住看杠杆翘起、挂钩松开摆锤")
def shB(t):
    b = tpos("ball1", min(t, 7.45))
    hold = at((lv["cup_x"] + lv["hook_x"]) / 2, 0, lv["z"] - 0.02)
    tg = lerp(at(b[0] + 0.12, 0, b[2] - 0.08), hold, ease(t, 7.0, 7.7))
    return tg, lerp(0.95, 1.05, ease(t, 7.0, 7.7)), 6, 0, 60, 8, lerp(b, hold, ease(t, 7.3, 7.6))

@S("C 摆锤全景", C[2], C[3], 0.20, 0.2, "动作剪：挂钩一松立刻切到 35 mm 固定侧面全景，完整看到 1 m 长摆锤画出的弧线和它击中第一张骨牌")
def shC(t):
    pv = pd["pivot"]; return at(pv[0] - 0.22, 0, (pv[1] + zD_) / 2 - 0.05), 2.6, 3, 0, 35, 11, at(pv[0], 0, pd["zc"])

@S("D 骨牌低机位横移", C[3], C[4], 0.10, 0.5, "70 mm 低机位（仰角 5°）、斜 18° 看骨牌队列，镜头与倒下的波前同速横移；骨牌越来越大，镜头随之后退")
def shD(t):
    w = wave(t); u = ease(t, 9.0, 11.5)
    return at(w + 0.10, 0, zD_ + lerp(0.04, 0.07, u)), lerp(0.85, 1.25, u), 5, 18, 70, 8, at(w, 0, zD_ + 0.04)

@S("E 扳机板→牛顿摆→玻璃管→陶瓷碗", C[4], C[5], 0.10, 0.5, "先停住看木块砸下扳机板、挂钩翻开、牛顿摆第一声与末球撞出玻璃珠（85 mm 固定）；再跟着玻璃珠横移经过 6 根玻璃管（60 mm），转为略俯视看它在 15 只碗上弹跳（50 mm），最后在天平托盘上方停稳")
def shE(t):
    xs = P["cradle"]["xs"]; c0 = at((P["cradle"]["plate"][0] + xs[-1]) / 2 + 0.02, 0, zD_ + 0.12)
    if t < 12.45:
        return c0, 1.0, 7, 0, 85, 8, at(xs[2], 0, P["cradle"]["zc"])
    m = tpos("marble0", min(t, 19.7)); u1 = ease(t, 12.45, 13.0); u2 = ease(t, 15.4, 16.2); u3 = ease(t, 19.2, 19.8)
    glass_tg = at(m[0] + 0.10, 0, gl_["z"] + 0.13); bowl_tg = at(m[0] + 0.15, 0, lerp(0.42, 0.24, ease(t, 16, 19.5)))
    pan_tg = at(P["balance"]["pan_x"] + 0.06, 0, P["balance"]["pan_z"] + 0.06)
    tg = lerp(lerp(lerp(c0, glass_tg, u1), bowl_tg, u2), pan_tg, u3)
    dist = lerp(lerp(lerp(1.0, 1.0, u1), 1.15, u2), 1.0, u3)
    return tg, dist, lerp(lerp(7, 6, u1), 16, u2), 0, lerp(lerp(85, 60, u1), 50, u2), 8, m

@S("F 天平微距 → 拉开", C[5], C[6], 0.10, 0.45, "切到 100 mm 微距、30° 俯角看进碟子：玻璃珠带着速度砸进托盘，在碟里来回滚动、托盘下沉回弹；随后慢慢拉开并转焦到上方的配重挂钩，观众看到横梁在油阻尼下慢慢倾斜，直到挂钩脱开")
def shF(t):
    bl_ = P["balance"]; pan = at(bl_["pan_x"], 0, bl_["pan_z"] + 0.012); u = ease(t, 21.3, 23.4)   # 30° 俯角才能看进碟子（碟深约 19 mm）
    top = at((bl_["pivot_x"] + wt_["x"]) / 2 + 0.02, 0, 0.50)
    fp = lerp(tpos("marble0", t), at(wt_["x"], 0.06, wt_["top"]), ease(t, 21.8, 23.2))
    return lerp(pan, top, u), lerp(0.48, 1.55, u), lerp(30, 6, u), lerp(-10, 0, u), lerp(100, 55, u), lerp(11, 8, u), fp

@S("G 配重下落 → 水瓶琴卡农 → 风铃井", C[6], C[7], 0.12, 0.6, "50 mm：配重脱钩、绳子绷紧（24.0 s 重拍）时镜头静止；第一颗珠落下后慢慢向右横移（比珠子慢），5 颗珠子错开一拍走过 8 只水瓶，自然叠成和弦；结束时停在风铃井和扳机杯上")
def shG(t):
    a = at((wt_["x"] + dp_["x"]) / 2, 0, 0.55); b0 = bt_["list"][0]["x"]; b7 = bt_["list"][-1]["x"]
    u = ease(t, 24.5, 29.6)
    tg = lerp(a, at(lerp(b0 + 0.35, tc_["x"] - 0.05, 1.0), 0, 0.40), u) if True else a
    lead = tpos("m1", t) if t < 28.3 else tpos("m5", t)
    return tg, lerp(1.35, 1.55, u), lerp(5, 10, u), 0, 50, 8, at(lead[0], 0, lead[2])

@S("H 扳机杯微距", C[7], C[8], 0.10, 0.3, "切到 60 mm 固定近景：满载的杯子缓缓下沉、脱扣“咔”的一下，弹射臂开始转动——让观众在发射前一刻先看清是谁触发了它")
def shH(t):
    return at(tc_["x"] + 0.13, 0, 0.20), 0.85, 7, 12, 60, 11, at(tc_["x"] + 0.02, 0, 0.16)

@S("I 弹射飞行全景", C[8], C[9], 0.35, 0.2, "动作剪到 35 mm 固定全景，整条抛物线和接球槽同在画面里；这一镜唯一保留明显动态模糊（快门 0.35），4 m/s 的铜球留下短拖影，读出速度")
def shI(t):
    pv = ca["pivot"]; fx = fu["c"][0]
    return at((pv[0] + fx) / 2 - 0.05, 0.1, 0.42), 2.1, 6, 0, 35, 11, at((pv[0] + fx) / 2, 0.1, 0.4)

@S("J 铜漏斗俯拍", C[9], C[10], 0.10, 0.6, "平静的拍子给一个高位俯拍：55° 俯角 50 mm（正上方会把头顶灯光整片反射进铜面），铜球绕着漏斗 3.5 圈越转越快，镜头只做 25° 的缓慢旋转")
def shJ(t):
    c = at(fu["c"][0], fu["c"][1], fu["z_rim"] - 0.1)
    return c, 1.1, 55, lerp(-20, 5, (t - C[9]) / (C[10] - C[9])), 50, 8, at(fu["c"][0], fu["c"][1], fu["z_rim"] - 0.05)

@S("K 铜钟 → 收尾 → 回望全景", C[10], C[11], 0.12, 0.6, "50 mm 固定侧面看铜球落到扳机板、钟锤荡下敲响铜钟（36.0 s）；钟声里镜头慢慢跟着铜球滚进木杯（39.5 s）；最后 4 秒升起，绕到机器右端沿台面回望全长，广角只在这个最平静的结尾出现")
def shK(t):
    b0 = at(be["x"] - 0.12, 0.12, be["zc"] - 0.02)
    if t < 37.0: return b0, 1.35, 8, 0, 50, 8, at(be["x"] - 0.1, be["y"], be["zc"])
    b = tpos("ball2", min(t, 39.6)); u1 = ease(t, 37.0, 37.8)
    fol = at(b[0] - 0.05, 0.15, 0.10)
    T_end = np.array([P["length"] * 0.42, 0.30, 0.42]); C_end = np.array([P["length"] + 0.9, -1.45, 1.30])
    off = C_end - T_end; d_end = float(np.linalg.norm(off)); el_end = math.degrees(math.asin(off[2] / d_end)); az_end = math.degrees(math.atan2(off[0], -off[1]))
    u2 = ease(t, 39.9, 43.4)
    tg = lerp(lerp(b0, fol, u1), T_end, u2)
    return tg, lerp(lerp(1.35, 1.0, u1), d_end, u2 ** 1.2), lerp(8, el_end, u2), lerp(0, az_end, u2), lerp(50, 28, u2), lerp(8, 11, u2), lerp(b, np.array([P["length"] * 0.7, 0.2, 0.4]), u2)

def gsmooth(a, sigma_s, hz):
    sig = max(1e-3, sigma_s * hz); k = np.arange(-int(4 * sig), int(4 * sig) + 1); w = np.exp(-0.5 * (k / sig) ** 2); w /= w.sum()
    pad = len(k) // 2
    if a.ndim == 1:
        ap = np.concatenate([np.full(pad, a[0]), a, np.full(pad, a[-1])]); return np.convolve(ap, w, mode="valid")
    return np.stack([gsmooth(a[:, i], sigma_s, hz) for i in range(a.shape[1])], 1)
HZ = 96
cam_d = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
cam.rotation_mode = 'QUATERNION'; cam_d.sensor_width = 36; cam_d.dof.use_dof = True; cam_d.clip_start = 0.02; cam_d.clip_end = 100
ALL_T, POS, QS, LE_, FD_, FS_, LAST = [], [], [], [], [], [], []
shot_log = []
for (name, t0, t1, f, shutter, sig, note) in SHOTS:
    ts = np.arange(t0, t1, 1 / HZ); ts = np.append(ts, t1 - 1e-4) if t1 - ts[-1] > 1e-4 else ts
    raw = [f(t) for t in ts]
    TG = gsmooth(np.array([r[0] for r in raw]), sig, HZ); DI = gsmooth(np.array([r[1] for r in raw], float), sig, HZ)
    EL = gsmooth(np.array([r[2] for r in raw], float), sig, HZ); AZ = gsmooth(np.array([r[3] for r in raw], float), sig, HZ)
    LEs = gsmooth(np.array([r[4] for r in raw], float), sig, HZ); FSs = np.array([r[5] for r in raw], float)
    FP = gsmooth(np.array([r[6] for r in raw]), 0.12, HZ)
    q_prev = None
    for i, t in enumerate(ts):
        el = math.radians(EL[i]); az = math.radians(AZ[i])
        off = np.array([math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)]) * DI[i]
        pos = TG[i] + off; q = Vector(tuple(TG[i] - pos)).to_track_quat('-Z', 'Y')
        if q_prev is not None and q.dot(q_prev) < 0: q = -q
        q_prev = q
        ALL_T.append(t); POS.append(pos); QS.append(q); LE_.append(LEs[i]); FD_.append(float(np.linalg.norm(FP[i] - pos))); FS_.append(FSs[i])
    LAST.append(len(ALL_T) - 1)
    # 相对速度检查：镜头本身的平移速度（m/s）与转动速度（°/s）
    P_ = np.array(POS[-len(ts):]); vcam = np.linalg.norm(np.diff(P_, axis=0), axis=1) * HZ
    shot_log.append(dict(shot=name, t0=round(t0, 4), t1=round(t1, 4), shutter=shutter, lens=[round(float(LEs.min())), round(float(LEs.max()))],
                         max_cam_speed_mps=round(float(vcam.max()), 3) if len(vcam) else 0, note=note))
frames_c = [fr(t) for t in ALL_T]; POS = np.array(POS)
def key_cut(o, chans):
    cb = _bl._cb(o)
    for (path, idx), vals in chans.items():
        fc = cb.fcurves.new(path, index=idx); fc.keyframe_points.add(len(frames_c))
        co = [0.0] * (2 * len(frames_c)); co[0::2] = frames_c; co[1::2] = [float(v) for v in vals]
        fc.keyframe_points.foreach_set("co", co)
        ip = [1] * len(frames_c)
        for j in LAST: ip[j] = 0          # 0 = CONSTANT：镜头末帧保持到剪切点，硬切
        fc.keyframe_points.foreach_set("interpolation", ip); fc.update()
ch = {("location", i): list(POS[:, i]) for i in range(3)}
ch.update({("rotation_quaternion", i): [q[i] for q in QS] for i in range(4)})
key_cut(cam, ch)
key_cut(cam_d, {("lens", 0): LE_, ("dof.focus_distance", 0): FD_, ("dof.aperture_fstop", 0): FS_})
# 动态模糊：按镜头设置快门（剪切点在两帧正中，快门 ≤ 0.35 帧时不会跨越剪切）
r_ = sc.render; r_.use_motion_blur = True
fr_sh = [fr(s_[1]) for s_ in SHOTS]; vals_sh = [s_[4] for s_ in SHOTS]
cbs = _bl._cb(sc)
fcs = cbs.fcurves.new("render.motion_blur_shutter"); fcs.keyframe_points.add(len(fr_sh))
co = [0.0] * (2 * len(fr_sh)); co[0::2] = fr_sh; co[1::2] = vals_sh
fcs.keyframe_points.foreach_set("co", co); fcs.keyframe_points.foreach_set("interpolation", [0] * len(fr_sh)); fcs.update()
json.dump(dict(shots=shot_log, t=ALL_T[::4], pos=POS[::4].tolist(), lens=LE_[::4]), open(os.path.join(PH.BUILD, "camera.json"), "w"), ensure_ascii=False, indent=0)
print("CAMERA_V2", len(SHOTS), "shots;", [(s_["shot"][:1], s_["max_cam_speed_mps"]) for s_ in shot_log])

# ---------------- 灯光 ----------------
w = bpy.data.worlds.new("world"); sc.world = w; w.use_nodes = True; nt = w.node_tree
env = nt.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(os.path.join(ROOT, "assets", "hdri", "artist_workshop_2k.hdr"))
bg = nt.nodes["Background"]; bg.inputs["Strength"].default_value = 0.22
nt.links.new(env.outputs["Color"], bg.inputs["Color"])
# v2：HDRI 只用于照明与反射；镜头直接看到的“天空”换成近黑色（去掉 v1 收尾广角里像“隔壁房间”的环境图）
bg2 = nt.nodes.new("ShaderNodeBackground"); bg2.inputs["Color"].default_value = (0.006, 0.0055, 0.005, 1)
lp = nt.nodes.new("ShaderNodeLightPath"); mx = nt.nodes.new("ShaderNodeMixShader")
outn = nt.nodes["World Output"]
nt.links.new(lp.outputs["Is Camera Ray"], mx.inputs[0]); nt.links.new(bg.outputs[0], mx.inputs[1]); nt.links.new(bg2.outputs[0], mx.inputs[2])
nt.links.new(mx.outputs[0], outn.inputs["Surface"])
def area(name, loc, size, power, col, aim, shape='RECTANGLE', sy=None):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = power; ld.color = col; ld.shape = shape; ld.size = size
    if sy: ld.size_y = sy
    o = bpy.data.objects.new(name, ld); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); link(o, "lights")
    o.visible_camera = False; return o
Lx = P["length"]
for i, x in enumerate(np.arange(-0.5, Lx + 1.0, 2.6)):
    area(f"window{i}", (x - 0.6, 0.62, 2.3), 2.4, 170, (0.82, 0.90, 1.0), (x + 0.2, -0.3, 0.3), sy=1.0)
for i, x in enumerate(np.arange(0.5, Lx + 1.0, 3.6)):
    area(f"fill{i}", (x, -3.8, 1.6), 3.5, 90, (1.0, 0.95, 0.88), (x, 0.3, 0.5), sy=2.0)
for i, x in enumerate([-0.2, 3.0, 6.6, 10.4, 13.9]):
    ld = bpy.data.lights.new(f"lamp{i}", 'POINT'); ld.energy = 30; ld.color = (1.0, 0.70, 0.42); ld.shadow_soft_size = 0.025
    o = bpy.data.objects.new(f"lamp{i}", ld); sc.collection.objects.link(o); o.location = (x, 0.05, 1.98); link(o, "lights")
    sphere(f"bulb{i}", (x, 0.05, 1.98), 0.028, emission("bulb", (1.0, 0.70, 0.42), 25), "lights", segs=24)
    lathe(f"shade{i}", [(0.035, 2.03), (0.07, 2.0), (0.12, 1.94)], (x, 0.05, 0), M["brass"], 48, "lights", thick=0.0015)
    rod(f"lamp_cord{i}", (x, 0.05, 2.03), (x, 0.05, 3.0), 0.003, M["black"], "lights")

# ---------------- 渲染设置（成片 Cycles） ----------------
r = sc.render; r.engine = 'CYCLES'; r.resolution_x, r.resolution_y, r.resolution_percentage = TL.WIDTH, TL.HEIGHT, 100
r.use_motion_blur = True   # 快门值按镜头关键帧设置（见摄影部分）
r.use_persistent_data = True
cy = sc.cycles; cy.device = 'GPU'; cy.samples = 128; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.015
cy.use_denoising = True; cy.denoiser = 'OPENIMAGEDENOISE'; cy.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
cy.max_bounces = 8; cy.diffuse_bounces = 3; cy.glossy_bounces = 4; cy.transmission_bounces = 10; cy.transparent_max_bounces = 8
cy.caustics_reflective = False; cy.caustics_refractive = False; cy.sample_clamp_indirect = 6.0; cy.blur_glossy = 1.0
try:
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception as e: print("look", e)
sc.view_settings.exposure = 0.0
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGB'; r.image_settings.compression = 15
r.filepath = os.path.join(ROOT, "renders", "final", "frame_")
r.use_overwrite = False; r.use_placeholder = True
ee = sc.eevee
try: ee.use_raytracing = True
except Exception: pass
ee.taa_render_samples = 24
