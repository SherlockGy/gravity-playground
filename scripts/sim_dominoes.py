# 重力乐园 · 骨牌段 Bullet 刚体仿真 + 自动调间距
# 用法: Blender -b --factory-startup -P scripts/sim_dominoes.py
# 以 120 Hz 记录（每帧 8 子步 = 960 Hz 求解），二分搜索骨牌间距系数 k，
# 使大木块落到扳机板的时刻 = timeline.BLOCK_LAND，结果写入 build/domino_sim.{json,npz}
import bpy, sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import timeline as TL, physics as PH

HZ = 120; SUB = 8; T0 = TL.PEND_RELEASE + 0.30; T1 = TL.BLOCK_LAND + 0.65
N = int(round((T1 - T0) * HZ)) + 1

def build_and_run(k, record=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.render.fps = HZ; sc.frame_start = 1; sc.frame_end = N

    PH_P = PH_design(k)
    doms = PH_P["dominoes"]; zD = PH_P["zD"]; head = PH_P["head_fn"]; hr = PH_P["pendulum"]["head_r"]
    bpy.ops.rigidbody.world_add(); rw = sc.rigidbody_world
    rw.substeps_per_frame = SUB; rw.solver_iterations = 40
    rw.point_cache.frame_start = 1; rw.point_cache.frame_end = N
    def add_box(name, loc, dims, passive=False, mass=1, fr=0.4, rest=0.15, margin=0.0004, kin=False):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.object; o.name = name
        o.scale = dims; bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.ops.rigidbody.object_add(); rb = o.rigid_body
        rb.type = 'PASSIVE' if passive else 'ACTIVE'; rb.collision_shape = 'BOX'
        rb.friction = fr; rb.restitution = rest; rb.use_margin = True; rb.collision_margin = margin
        if not passive: rb.mass = mass
        rb.kinematic = kin
        o.select_set(False); return o
    x_first = doms[0]["x"]; blk = doms[-1]["x"] + doms[-1]["t"]
    add_box("shelf", ((x_first + blk) / 2, 0, zD - 0.02), (blk - x_first + 0.8, 0.3, 0.04), passive=True, fr=0.5)
    add_box("plate", (blk + 0.11, 0, zD + 0.002), (0.05, 0.05, 0.004), passive=True, fr=0.5, rest=0.1)
    objs = []
    for d in doms:
        o = add_box(f"dom{d['i']}", (d["x"] + d["t"] / 2, 0, zD + d["h"] / 2 + 0.0002), (d["t"], d["w"], d["h"]),
                    mass=d["mass"], fr=0.35 if d["mat"] == "porcelain" else 0.45, rest=0.2 if d["mat"] == "porcelain" else 0.12)
        objs.append(o)
    # 运动学摆锤头（圆柱，轴沿 y）
    bpy.ops.mesh.primitive_cylinder_add(radius=hr, depth=0.06, vertices=24, rotation=(math.pi / 2, 0, 0))
    hd = bpy.context.object; hd.name = "head"
    bpy.ops.rigidbody.object_add(); hd.rigid_body.type = 'ACTIVE'; hd.rigid_body.kinematic = True
    hd.rigid_body.collision_shape = 'CONVEX_HULL'; hd.rigid_body.use_margin = True; hd.rigid_body.collision_margin = 0.0004
    for f in range(1, N + 1):
        t = T0 + (f - 1) / HZ; x, z = head(t)
        hd.location = (x, 0, z); hd.keyframe_insert("location", frame=f)
    ts = np.array([T0 + (f - 1) / HZ for f in range(1, N + 1)])
    L = np.zeros((N, len(objs), 3)); Q = np.zeros((N, len(objs), 4))
    for f in range(1, N + 1):
        sc.frame_set(f)
        for j, o in enumerate(objs):
            m = o.matrix_world; L[f - 1, j] = m.translation; Q[f - 1, j] = m.to_quaternion()
    return ts, L, Q, doms, blk

def PH_design(k):
    PH.CONTACTS.clear()
    P, _ = PH.design.__globals__["design_k"](k)
    return P

def design_k(k):
    # 只要 A 段（到骨牌为止）：临时屏蔽仿真结果
    real = PH.load_sim; PH.load_sim = lambda: None
    old = PH.domino_spec
    PH.domino_spec = lambda x, z, kk=None: old(x, z, k)
    try: P, T = PH.design()
    finally: PH.load_sim = real; PH.domino_spec = old
    return P, T
PH.design.__globals__["design_k"] = design_k

def tilt(q):  # 局部 z 轴与竖直方向夹角（度），带符号（向 +x 倒为正）
    w, x, y, z = q
    zx = 2 * (x * z + w * y); zz = 1 - 2 * (x * x + y * y)
    return math.degrees(math.atan2(zx, zz))

def analyse(ts, L, Q, doms):
    n = len(doms); ang = np.array([[tilt(Q[f, j]) for j in range(n)] for f in range(len(ts))])
    onset = []
    for j in range(n):
        idx = np.where(ang[:, j] > 1.0)[0]
        if len(idx) == 0: onset.append(None); continue
        f = idx[0]
        # 向前外推：倒下初期角度近似线性增长，用相邻两帧斜率回推到 0.0 度
        if f + 1 < len(ts):
            slope = (ang[f + 1, j] - ang[f, j]) * HZ
            t_on = ts[f] - ang[f, j] / slope if slope > 1e-3 else ts[f]
        else: t_on = ts[f]
        onset.append(float(max(ts[0], min(ts[f], t_on))))
    # 大木块落到扳机板：倾角超过 60 度后角速度骤降的时刻
    jb = n - 1; a = ang[:, jb]; w = np.gradient(a, ts)
    land = None
    for f in range(2, len(ts) - 1):
        if a[f] > 55 and w[f - 1] > 50 and w[f + 1] < 0.5 * w[f - 1]:
            # 在 f-1..f+1 之间按角速度骤降点线性插值
            land = float(ts[f - 1] + (ts[f] - ts[f - 1]) * 0.5); break
    return onset, land, ang

def run_k(k):
    ts, L, Q, doms, blk = build_and_run(k)
    onset, land, ang = analyse(ts, L, Q, doms)
    fallen = sum(1 for o in onset if o is not None)
    return dict(k=k, land=land, fallen=fallen, onset=onset, ts=ts, L=L, Q=Q, doms=doms, blk=blk, ang=ang)

target = TL.BLOCK_LAND
lo, hi = 0.55, 0.88; best = None; log = []
for it in range(12):
    k = (lo + hi) / 2; r = run_k(k)
    ok = r["fallen"] == PH.N_DOMINO and r["land"] is not None
    log.append((round(k, 5), r["fallen"], r["land"]))
    print("ITER", it, k, r["fallen"], r["land"], flush=True)
    if not ok:
        hi = k; continue   # 间距过大 -> 链断，缩小
    best = r if best is None or abs(r["land"] - target) < abs(best["land"] - target) else best
    if abs(r["land"] - target) < 0.004: break
    if r["land"] > target: hi = k
    else: lo = k
r = best
# 确定性复核：同参数再跑一次
r2 = run_k(r["k"])
det = float(np.max(np.abs(r2["L"] - r["L"])))
contacts = []
for j in range(1, PH.N_DOMINO):
    if r["onset"][j] is not None:
        contacts.append(dict(t=r["onset"][j], a=f"dom{j-1}", b=f"dom{j}"))
contacts.append(dict(t=r["land"], a=f"dom{PH.N_DOMINO-1}", b="cradle_plate"))
meta = dict(k=r["k"], block_land=r["land"], target=target, fallen=r["fallen"], hz=HZ, substeps=SUB,
            block_pivot_x=r["blk"], determinism_max_diff_m=det, search=log, contacts=contacts,
            doms=[dict(i=d["i"], x=d["x"], h=d["h"], t=d["t"], w=d["w"], mat=d["mat"], mass=d["mass"]) for d in r["doms"]])
os.makedirs(PH.BUILD, exist_ok=True)
json.dump(meta, open(os.path.join(PH.BUILD, "domino_sim.json"), "w"), indent=1)
np.savez_compressed(os.path.join(PH.BUILD, "domino_sim.npz"), t=r["ts"], loc=r["L"], quat=r["Q"])
print("SIM_RESULT", json.dumps(dict(k=r["k"], land=r["land"], target=target, fallen=r["fallen"], det=det)))
