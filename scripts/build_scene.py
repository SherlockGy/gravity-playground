# 重力乐园 · 场景构建（全部由脚本生成，可重复）
# 用法: Blender -b --factory-startup -P scripts/build_scene.py
# 读取 build/motion.json（physics.py 生成）与 build/domino_sim.npz，输出 blend/重力乐园.blend
import bpy, sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mathutils import Vector, Quaternion, Euler
import timeline as TL
import physics as PH
from blib import *

ROOT = PH.ROOT
D = json.load(open(os.path.join(PH.BUILD, "motion.json")))
P = D["P"]; TR = D["tracks"]
sim = np.load(os.path.join(PH.BUILD, "domino_sim.npz"))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = TL.FPS; sc.frame_start = 1; sc.frame_end = TL.FRAMES
sc.unit_settings.system = 'METRIC'
def fr(t): return 1 + t * TL.FPS
def note_f(n): return TL.NOTE[n]

# ---------------- 材质库 ----------------
M = dict(
    walnut=wood("walnut", "american_walnut_veneer", 3.0, (0.95, 0.60, 0.38), 0.9, coat=0.25, nstr=1.0),
    rosewood_dark=wood("rosewood_dark", "cherry_veneer", 4.0, (0.25, 0.095, 0.06), 0.8, coat=0.45, nstr=1.2),
    walnut_dark=wood("walnut_dark", "american_walnut_veneer", 1.6, (0.62, 0.40, 0.27), 1.0, coat=0.1),
    maple=wood("maple", "ash_veneer", 2.0, (0.92, 0.80, 0.62), 0.9, coat=0.2),
    rosewood=wood("rosewood", "cherry_veneer", 6.0, (0.85, 0.38, 0.22), 0.8, coat=0.35, nstr=1.0),
    planks=wood("planks", "brown_planks_05", 0.8, (0.30, 0.27, 0.24), 1.0),
    brass=metal("brass", (0.88, 0.66, 0.36), 0.16, 0.32, tarnish=(0.36, 0.26, 0.14)),
    brass_pol=metal("brass_pol", (0.93, 0.74, 0.42), 0.08, 0.16),
    steel=metal("steel", (0.78, 0.78, 0.8), 0.04, 0.1, scale=120),
    steel_ball=metal("steel_ball", (0.80, 0.80, 0.82), 0.09, 0.13, scale=120),   # v4：抛光钢球略加粗糙度，反射不再是纯镜面，球体更像实体
    copper=metal("copper", (0.93, 0.55, 0.40), 0.18, 0.32, tarnish=(0.35, 0.18, 0.12)),
    copper_spun=metal("copper_spun", (0.88, 0.47, 0.30), 0.20, 0.28),   # 漏斗：旋压紫铜，大面积不做氧化斑（俯拍时斑点读成污渍）
    iron=metal("iron", (0.10, 0.10, 0.105), 0.5, 0.75, tarnish=(0.22, 0.10, 0.05), scale=30),
    blued=metal("blued", (0.10, 0.13, 0.20), 0.22, 0.35),
    glass=glass("glass"),
    bottle_g=glass("bottle_green", (0.62, 0.82, 0.68), 0.01),
    bottle_a=glass("bottle_amber", (0.85, 0.55, 0.25), 0.01),
    bottle_c=glass("bottle_clear", (0.93, 0.97, 0.98), 0.01),
    marble=glass("marble", (0.55, 0.78, 0.95), 0.0),
    water=glass("water", (0.9, 0.97, 1.0), 0.0, 1.333),
    porcelain=dielectric("porcelain", (0.90, 0.89, 0.86), 0.3, coat=1.0, coat_rough=0.04, sss=0.05),
    felt=dielectric("felt", (0.30, 0.05, 0.05), 0.95, sheen=1.0),
    felt_g=dielectric("felt_green", (0.06, 0.16, 0.10), 0.95, sheen=1.0),
    string=dielectric("string", (0.85, 0.82, 0.75), 0.8),
    rope=dielectric("rope", (0.55, 0.43, 0.28), 0.85, sheen=0.5),
    black=dielectric("black_lacquer", (0.02, 0.02, 0.02), 0.25, coat=0.5),
)
GLAZE = [dielectric("glaze_celadon", (0.50, 0.66, 0.56), 0.3, coat=1, coat_rough=0.05),
         dielectric("glaze_cream", (0.88, 0.83, 0.70), 0.3, coat=1, coat_rough=0.05),
         dielectric("glaze_indigo", (0.10, 0.16, 0.34), 0.3, coat=1, coat_rough=0.05),
         dielectric("glaze_rust", (0.55, 0.26, 0.14), 0.3, coat=1, coat_rough=0.05)]
# v2：去掉砖墙，改为暗色无缝背景布（低对比、微弱的灰泥起伏，越往上越暗），让视线留在机关上
m = bpy.data.materials.new("backdrop"); m.use_nodes = True; nt = m.node_tree; p = nt.nodes["Principled BSDF"]
tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 2.5; nz.inputs["Detail"].default_value = 6
nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
gz = nt.nodes.new("ShaderNodeMapRange"); gz.inputs["From Min"].default_value = -1.0; gz.inputs["From Max"].default_value = 2.5
gz.inputs["To Min"].default_value = 1.0; gz.inputs["To Max"].default_value = 0.35; nt.links.new(sep.outputs["Z"], gz.inputs["Value"])
nr = nt.nodes.new("ShaderNodeMapRange"); nr.inputs["To Min"].default_value = 0.85; nr.inputs["To Max"].default_value = 1.12; nt.links.new(nz.outputs["Fac"], nr.inputs["Value"])
m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = 'MULTIPLY'; nt.links.new(gz.outputs["Result"], m1.inputs[0]); nt.links.new(nr.outputs["Result"], m1.inputs[1])
m2 = nt.nodes.new("ShaderNodeMix"); m2.data_type = 'RGBA'; m2.blend_type = 'MULTIPLY'; m2.inputs["Factor"].default_value = 1
m2.inputs[6].default_value = (0.022, 0.019, 0.017, 1); nt.links.new(m1.outputs[0], m2.inputs[7]); nt.links.new(m2.outputs[2], p.inputs["Base Color"])
p.inputs["Roughness"].default_value = 0.95
bmp = nt.nodes.new("ShaderNodeBump"); bmp.inputs["Strength"].default_value = 0.08; nt.links.new(nz.outputs["Fac"], bmp.inputs["Height"]); nt.links.new(bmp.outputs["Normal"], p.inputs["Normal"])
M["backdrop"] = m

# ---------------- 环境 ----------------
L = P["length"]
box("bench_top", (L / 2 - 0.3, 0.15, -0.035), (L + 2.4, 1.1, 0.07), M["walnut"], 0.004, "env")
box("bench_apron", (L / 2 - 0.3, -0.38, -0.12), (L + 2.4, 0.04, 0.12), M["walnut_dark"], 0.003, "env")
# 背景布：台面后方 1.6 m，宽度远超机器全长；在镜头里始终处于焦外
box("backdrop", (L / 2 - 0.3, 1.75, 1.5), (L + 40, 0.04, 6.0), M["backdrop"], 0, "env")
box("floor", (L / 2 - 0.3, -2.5, -0.95), (L + 40, 8.6, 0.04), M["planks"], 0, "env")
for x in np.arange(-0.9, L + 1.3, 2.4):
    box(f"bench_leg{x:.1f}", (x, -0.3, -0.5), (0.07, 0.07, 0.9), M["walnut_dark"], 0.003, "env")

# ================= ① 节拍器 / ② 滚轨 / ③ 台阶 =================
zD = P["zD"]; r1 = P["r_steel"]
mt = P["metronome"]; rail = P["rail"]; steps = P["stairs"]
tower_top = 1.42
box("tower", (-0.04, 0, (zD + tower_top) / 2), (1.02, 0.16, tower_top - zD), M["walnut"], 0.003, "stage1")
# 节拍器：梯形木壳 + 摆杆
mx = mt["x"]
lathe("metro_body", [(0.065, 0), (0.060, 0.02), (0.030, 0.20), (0.012, 0.215)], (mx, 0, tower_top), M["black"], 4, "stage1",
      props=dict(snd="woodblock"))
bpy.data.objects["metro_body"].rotation_euler = (0, 0, math.pi / 4)
box("metro_face", (mx, -0.032, tower_top + 0.11), (0.05, 0.004, 0.16), M["walnut_dark"], 0.001, "stage1")
arm = empty("metro_arm", (mx, -0.04, tower_top + 0.035))
rod("metro_rod", (mx, -0.04, tower_top + 0.035), (mx, -0.04, tower_top + 0.235), 0.0018, M["steel"], "stage1", arm)
cyl("metro_weight", (mx, -0.04, tower_top + 0.16), 0.008, 0.022, "z", M["brass_pol"], 24, 0.001, "stage1", arm)
rod("metro_pin", (mx, -0.04, tower_top + 0.06), (mx + 0.075, -0.04, tower_top + 0.06), 0.0015, M["brass"], "stage1", arm)
# 棘轮（8 齿）
rx = -0.11; rz = tower_top + 0.045
rt = empty("ratchet", (rx, -0.04, rz))
import bmesh
me = bpy.data.meshes.new("ratchet_wheel"); bm = bmesh.new()
pts = []
for i in range(16):
    a = 2 * math.pi * i / 16; rr = 0.030 if i % 2 == 0 else 0.022
    pts.append((rr * math.cos(a), rr * math.sin(a)))
vb = [bm.verts.new((x, -0.004, z)) for x, z in pts]; vf = [bm.verts.new((x, 0.004, z)) for x, z in pts]
bm.faces.new(vb); bm.faces.new(list(reversed(vf)))
for i in range(16): bm.faces.new((vb[i], vb[(i + 1) % 16], vf[(i + 1) % 16], vf[i]))
bm.normal_update(); bm.to_mesh(me); bm.free()
o = bpy.data.objects.new("ratchet_wheel", me); sc.collection.objects.link(o); o.location = (rx, -0.04, rz)
o.data.materials.append(M["brass"]); link(o, "stage1"); set_parent(o, rt)
o.modifiers.new("bev", "BEVEL").width = 0.0006
cyl("ratchet_axle", (rx, -0.02, rz), 0.004, 0.05, "y", M["steel"], 16, 0, "stage1")
box("ratchet_post", (rx, -0.0, tower_top + 0.022), (0.02, 0.03, 0.045), M["walnut_dark"], 0.001, "stage1")
# v5：脱扣机构。棘轮正面的拨销（随棘轮转）→ 脱扣杠杆（y=-0.05 平面，中间铰接）→ 挡板尾杆 → 挡板翻开
tp = P["trip"]; FX = tp["flap_x"]; zf = rail["z0"] + 0.032; yL = -0.05
pa = math.radians(tp["pin_a0"])
rod("trip_pin", (rx + tp["pin_r"] * math.cos(pa), -0.044, rz + tp["pin_r"] * math.sin(pa)), (rx + tp["pin_r"] * math.cos(pa), yL - 0.006, rz + tp["pin_r"] * math.sin(pa)), 0.0022, M["steel"], "stage1", rt)
tipL = (rx + 0.022, rz + tp["tip_dz"]); tipR = (FX - tp["tail"], zf + 0.0032)
pvx, pvz = (tipL[0] + tipR[0]) / 2, (tipL[1] + tipR[1]) / 2
tl_ = empty("trip_lever", (pvx, yL, pvz))
rod("trip_lever_bar", (tipL[0], yL, tipL[1]), (tipR[0], yL, tipR[1]), 0.0019, M["brass_pol"], "stage1", tl_, props=dict(snd="trip_lever"))
cyl("trip_lever_axle", (pvx, yL + 0.004, pvz), 0.003, 0.014, "y", M["steel"], 16, 0, "stage1")
rod("trip_lever_post", (pvx, yL + 0.012, tower_top), (pvx, yL + 0.012, pvz), 0.0035, M["walnut_dark"], "stage1")
# 放行挡板（上端铰接）：钢珠静止时贴着挡板
fl = empty("flap", (FX, 0, zf))
box("flap_plate", (FX, 0, rail["z0"] + 0.016), (0.003, 0.03, 0.032), M["brass_pol"], 0.0006, "stage1", fl, props=dict(snd="brass"))
rod("flap_tail", (FX, 0, zf), (FX - tp["tail"], 0, zf), 0.0015, M["brass"], "stage1", fl)
rod("flap_tail_y", (FX - tp["tail"], 0, zf), (FX - tp["tail"], yL - 0.004, zf), 0.0015, M["brass"], "stage1", fl)
box("flap_bracket", (FX, 0.022, rail["z0"] + 0.04), (0.01, 0.006, 0.02), M["brass"], 0.0006, "stage1")
# 枫木滚轨（带槽）
rl = math.hypot(rail["x1"] - rail["x0"], rail["z0"] - rail["z1"]); ang = math.radians(rail["slope_deg"])
cx = (rail["x0"] + rail["x1"]) / 2; cz = (rail["z0"] + rail["z1"]) / 2 - 0.015
for side in (-1, 1):
    box(f"rail_{side}", (cx, side * 0.010, cz + 0.003), (rl, 0.012, 0.034), M["maple"], 0.0015, "stage1", rot=(0, ang, 0), props=dict(snd="maple"))
box("rail_bed", (cx, 0, cz - 0.004), (rl, 0.034, 0.022), M["maple"], 0.0015, "stage1", rot=(0, ang, 0), props=dict(snd="maple"))
# 台阶 + 红木音条
for s in steps:
    k = s["k"]
    box(f"tread{k}", ((s["x0"] + s["x1"]) / 2, 0, (zD + s["ztop"]) / 2), (s["x1"] - s["x0"], 0.12, s["ztop"] - zD), M["rosewood_dark"], 0.006, "stage3",
        props=dict(snd="walnut"))
    f = note_f(s["note"]); blen = 0.17 * math.sqrt(880 / f) + 0.05
    box(f"bar{k}", (s["bar_x"], 0, s["ztop"] - 0.011 + 0.0005), (0.055, blen, 0.022), M["rosewood"], 0.002, "stage3",
        props=dict(snd="rosewood", note=s["note"]))
    for sy in (-1, 1):
        box(f"bar{k}_felt{sy}", (s["bar_x"], sy * 0.045, s["ztop"] - 0.0225), (0.06, 0.012, 0.004), M["felt"], 0.0005, "stage3")
# ================= ④ 杠杆 =================
lv = P["lever"]; px, pz = lv["pivot"]
box("lever_post", (px, 0.03, (zD + pz) / 2 - 0.006), (0.03, 0.02, pz - zD - 0.012), M["walnut_dark"], 0.002, "stage4")
lvr = empty("lever", (px, 0, pz))
box("lever_beam", (px, 0, pz - 0.006), (0.27, 0.018, 0.012), M["walnut_dark"], 0.0015, "stage4", lvr)
lathe("cup", [(0.0, 0), (0.024, 0.002), (0.028, 0.02), (0.030, 0.036)], (lv["cup_x"], 0, pz + 0.0), M["brass"], 48, "stage4", lvr,
      cap_bottom=False, thick=0.0025, props=dict(snd="brass_cup", note="A3"))
rod("lever_hook", (lv["hook_x"], 0, pz), (lv["hook_x"], 0, pz - 0.035), 0.003, M["brass"], "stage4", lvr)
box("lever_stop", (lv["cup_x"] + 0.03, 0, pz - 0.06), (0.02, 0.02, 0.06), M["felt"], 0.001, "stage4", props=dict(snd="felt"))
# ================= ⑤ 摆锤 =================
pd = P["pendulum"]; xp, zpv = pd["pivot"]; Lp = pd["L"]
for sy in (-1, 1):
    box(f"pend_upright{sy}", (xp, sy * 0.07, (zD + zpv + 0.05) / 2), (0.035, 0.025, zpv + 0.05 - zD), M["walnut"], 0.002, "stage5")
box("pend_top", (xp, 0, zpv + 0.03), (0.05, 0.17, 0.04), M["walnut"], 0.002, "stage5")
cyl("pend_axle", (xp, 0, zpv), 0.005, 0.15, "y", M["steel"], 16, 0, "stage5")
pe = empty("pendulum", (xp, 0, zpv))
rod("pend_rod", (xp, 0, zpv), (xp, 0, pd["zc"]), 0.0035, M["brass_pol"], "stage5", pe)
cyl("pend_head", (xp, 0, pd["zc"]), pd["head_r"], 0.06, "y", M["brass_pol"], 48, 0.001, "stage5", pe, props=dict(snd="brass"))
rod("pend_pin", (xp, -0.012, pd["zc"] + 0.03), (xp, 0.012, pd["zc"] + 0.03), 0.002, M["steel"], "stage5", pe)
box("pend_stop", (xp + 0.0035 + 0.006, 0, pd["zc"] + 0.30), (0.012, 0.12, 0.02), M["felt"], 0.001, "stage5", props=dict(snd="felt"))
# ================= ⑥ 骨牌 =================
meta = json.load(open(os.path.join(PH.BUILD, "domino_sim.json")))
sx0 = min(d["x"] for d in meta["doms"]) - 0.1; sx1 = P["cradle"]["xs"][-1] + 0.95
box("shelfB", ((sx0 + sx1) / 2 - 0.0, 0, zD - 0.015), (sx1 - sx0 + 0.0, 0.32, 0.03), M["walnut"], 0.003, "env",
    props=dict(snd="walnut"))
box("shelfB_tower", (-0.04, 0, zD - 0.015), (1.3, 0.32, 0.03), M["walnut"], 0.003, "env")
for x in list(np.arange(sx0 + 0.1, sx1, 1.2)) + [-0.5, 0.4]:
    for sy in (-1, 1):
        box(f"shelfB_leg_{x:.2f}_{sy}", (x, sy * 0.12, (zD - 0.03) / 2), (0.04, 0.04, zD - 0.03), M["walnut_dark"], 0.002, "env")
DOM_MAT = {"porcelain": M["porcelain"], "maple": M["maple"], "walnut": M["walnut"]}
doms = []
for d in meta["doms"]:
    o = box(f"dom{d['i']}", (0, 0, 0), (d["t"], d["w"], d["h"]), DOM_MAT[d["mat"]], min(0.0015, d["t"] * 0.12), "stage6",
            props=dict(snd="dom_" + d["mat"], mass=d["mass"], size=d["h"]))
    o.rotation_mode = 'QUATERNION'; doms.append(o)
# 扳机板 + 牛顿摆挂钩连杆
cr = P["cradle"]
plate_x0, plate_x1 = cr["plate"]
cp = empty("cradle_plate", (plate_x0, 0, zD + 0.004))
box("cradle_plate_mesh", ((plate_x0 + plate_x1) / 2, 0, zD + 0.002), (plate_x1 - plate_x0, 0.05, 0.004), M["brass"], 0.0006, "stage7", cp,
    props=dict(snd="brass"))
# ================= ⑦ 牛顿摆 =================
xs = cr["xs"]; top = cr["top"]; Lc = cr["L"]; rc = cr["rc"]
fx0, fx1 = xs[0] - 0.09, xs[-1] + 0.09
box("cradle_base", ((fx0 + fx1) / 2, 0, zD + 0.008), (fx1 - fx0 + 0.04, 0.16, 0.016), M["walnut_dark"], 0.002, "stage7")
for x in (fx0, fx1):
    for sy in (-1, 1):
        rod(f"cradle_post_{x:.2f}_{sy}", (x, sy * 0.065, zD + 0.016), (x, sy * 0.065, top + 0.004), 0.004, M["steel"], "stage7")
for sy in (-1, 1):
    rod(f"cradle_bar{sy}", (fx0, sy * 0.065, top + 0.004), (fx1, sy * 0.065, top + 0.004), 0.004, M["steel"], "stage7")
for j, x in enumerate(xs):
    pv = empty(f"cradle{j}", (x, 0, top))
    sphere(f"cradle_ball{j}", (x, 0, top - Lc), rc, M["steel_ball"], "stage7", pv, props=dict(snd="cradle", mass=P["masses"]["cradle"]))
    for sy in (-1, 1):
        rod(f"cradle_str{j}_{sy}", (x, sy * 0.065, top), (x, 0, top - Lc + rc * 0.8), 0.0004, M["string"], "stage7", pv, 6)
hk = empty("cradle_hook", (fx0, -0.03, top - Lc * math.cos(math.radians(15)) + 0.02))
rod("cradle_hook_rod", (fx0, -0.03, top - Lc * math.cos(math.radians(15)) + 0.02),
    (xs[0] - Lc * math.sin(math.radians(15)), -0.03, top - Lc * math.cos(math.radians(15)) + 0.02), 0.0015, M["brass"], "stage7", hk)
rod("cradle_link", (plate_x0 + 0.01, -0.03, zD + 0.006), (fx0, -0.03, top - Lc * math.cos(math.radians(15)) + 0.02), 0.0012, M["brass"], "stage7")
WOBBLE = []   # (物体, 被撞时刻列表, 振幅, 角频率, 衰减时间常数, 方向) —— 被撞物的阻尼摆动
# ================= ⑧ 玻璃管滚道 =================
gl = P["glass"]; rm = P["r_marble"]
gz = gl["z"] + rm - 0.0095
for sy in (-1, 1):
    rod(f"grail{sy}", (gl["x0"], sy * 0.0055, gz), (gl["x1"], sy * 0.0055, gz), 0.003, M["glass"], "stage8", None, 16,
        props=dict(snd="glass_rail"))
for i, x in enumerate(np.linspace(gl["x0"] + 0.05, gl["x1"] - 0.03, 6)):
    rod(f"grail_post{i}", (x, 0, 0), (x, 0, gz - 0.004), 0.004, M["brass"], "stage8")
    box(f"grail_saddle{i}", (x, 0, gz - 0.004), (0.01, 0.02, 0.006), M["brass"], 0.0008, "stage8")
rack_z = gl["z"] + rm + 0.36; ty = rm + 0.0085
rod("gtube_rack", (gl["x0"] + 0.1, ty, rack_z), (gl["taps"][-1]["x"] + 0.1, ty, rack_z), 0.004, M["brass"], "stage8")
for x in (gl["x0"] + 0.1, gl["taps"][-1]["x"] + 0.1):
    rod(f"gtube_rack_post{x:.2f}", (x, 0.06, 0), (x, 0.06, rack_z), 0.005, M["brass"], "stage8")
    rod(f"gtube_rack_arm{x:.2f}", (x, 0.06, rack_z), (x, ty, rack_z), 0.004, M["brass"], "stage8")
for k, tp in enumerate(gl["taps"]):
    f = note_f(tp["note"]); ln = 0.30 * math.sqrt(587 / f)
    zb = gl["z"] + rm - 0.002
    lathe(f"gtube{k}", [(0.0098, zb), (0.010, zb + 0.002), (0.010, zb + ln)], (0, 0, 0), M["glass"], 32, "stage8",
          thick=0.0012, props=dict(snd="glass_tube", note=tp["note"]))
    o = bpy.data.objects[f"gtube{k}"]; o.location = (tp["x"], rm + 0.010 - 0.0015, 0)
    pv = empty(f"gtube_pivot{k}", (tp["x"], ty, rack_z), "rigs")
    set_parent(o, pv)
    rod(f"gtube_str{k}", (tp["x"], ty, zb + ln), (tp["x"], ty, rack_z), 0.0004, M["string"], "stage8", pv, 6)
    WOBBLE.append((pv.name, [tp["t"]], math.radians(2.5), math.sqrt(9.81 / (rack_z - zb - ln / 2)), 1.6, +1))
# ================= ⑨ 陶瓷碗 =================
for k, b in enumerate(P["bowls"]):
    f = note_f(b["note"]); dd = 0.105 * (294 / f) ** 0.45; hh = 0.42 * dd
    zt = b["ztop"]
    prof = [(dd / 2, zt - hh), (dd / 2 * 0.97, zt - hh * 0.6), (dd / 2 * 0.8, zt - hh * 0.25), (dd * 0.32, zt - 0.006), (dd * 0.30, zt - 0.003), (dd * 0.29, zt)]
    lathe(f"bowl{k}", prof, (b["x"], 0, 0), GLAZE[k % 4], 64, "stage9", cap_bottom=False, thick=0.003,
          props=dict(snd="ceramic", note=b["note"]))
    cyl(f"bowl{k}_top", (b["x"], 0, zt - 0.0015), dd * 0.29, 0.003, "z", GLAZE[k % 4], 48, 0, "stage9")
    rod(f"bowl{k}_post", (b["x"], 0.0, 0), (b["x"], 0.0, zt - hh * 0.4), 0.004, M["brass"], "stage9")
# ================= ⑩ 天平 =================
bl = P["balance"]
rod("bal_post", (bl["pivot_x"], 0.0, 0), (bl["pivot_x"], 0.0, bl["pivot_z"]), 0.008, M["brass"], "stage10")
cyl("bal_foot", (bl["pivot_x"], 0, 0.006), 0.06, 0.012, "z", M["walnut_dark"], 48, 0.002, "stage10")
bm_ = empty("beam", (bl["pivot_x"], 0, bl["pivot_z"]))
box("beam_mesh", (bl["pivot_x"], 0, bl["pivot_z"]), (2 * bl["arm"] + 0.02, 0.008, 0.01), M["brass_pol"], 0.001, "stage10", bm_)
lathe("bal_needle", [(0.004, bl["pivot_z"]), (0.0005, bl["pivot_z"] + 0.09)], (bl["pivot_x"], 0, 0), M["steel"], 8, "stage10", bm_)
for nm_, xx in (("pan_l", bl["pan_x"]), ("pan_r", bl["pan_x"] + 2 * bl["arm"])):
    pn = empty(nm_, (xx, 0, bl["pan_z"]))
    Rc_ = bl.get("Rc", 0.06); z0_ = bl["pan_z"] - 0.0008
    lathe(nm_ + "_dish", [(r_, z0_ + r_ * r_ / (2 * Rc_)) for r_ in np.linspace(0, 0.048, 10)] + [(0.0505, z0_ + 0.048 ** 2 / (2 * Rc_) + 0.002)], (xx, 0, 0), M["brass"], 48, "stage10",
          pn, thick=0.0015, props=dict(snd="brass_pan", note="D6"))
    for i in range(3):
        a = 2 * math.pi * i / 3 + 0.3
        rod(f"{nm_}_str{i}", (xx + 0.046 * math.cos(a), 0.046 * math.sin(a), bl["pan_z"] + 0.048 ** 2 / (2 * Rc_)), (xx, 0, bl["pivot_z"] - 0.002), 0.0004, M["string"], "stage10", pn, 6)
# 油阻尼筒
cyl("damper", (bl["pivot_x"] - 0.07, 0.03, bl["pivot_z"] - 0.12), 0.012, 0.08, "z", M["brass"], 32, 0.001, "stage10")
rod("damper_rod", (bl["pivot_x"] - 0.07, 0.03, bl["pivot_z"] - 0.09), (bl["pivot_x"] - 0.07, 0.03, bl["pivot_z"]), 0.0015, M["steel"], "stage10", bm_)
rod("damper_arm", (bl["pivot_x"] - 0.07, 0.03, bl["pivot_z"]), (bl["pivot_x"] - 0.07, 0.0, bl["pivot_z"]), 0.0015, M["steel"], "stage10", bm_)
# ================= ⑪ 配重 + 分珠器 =================
wt = P["weight"]; xw = wt["x"]; dp = P["dispenser"]
rod("w_post", (xw + 0.06, 0.12, 0), (xw + 0.06, 0.12, wt["pulley_z"] + 0.06), 0.012, M["walnut_dark"], "stage11")
rod("w_beam", (xw + 0.06, 0.12, wt["pulley_z"] + 0.03), (xw - 0.0, 0.06, wt["pulley_z"] + 0.03), 0.006, M["brass"], "stage11")
cyl("w_pulley", (xw + 0.0 + 0.0, 0.06, wt["pulley_z"]), 0.03, 0.01, "y", M["brass"], 48, 0.001, "stage11")
we = empty("weight", (xw, 0.06, wt["top"]))
cyl("weight_mesh", (xw, 0.06, wt["top"] + 0.05), 0.035, 0.10, "z", M["iron"], 48, 0.002, "stage11", we, props=dict(snd="iron", mass=2.0))
rod("weight_hook", (xw, 0.06, wt["top"] + 0.10), (xw, 0.06, wt["top"] + 0.125), 0.003, M["steel"], "stage11", we)
box("felt_pad", (xw, 0.06, 0.005), (0.11, 0.11, 0.01), M["felt_g"], 0.002, "stage11", props=dict(snd="felt"))
lp = empty("latch_pin", (xw, 0.06, wt["top"] + 0.05))
rod("latch_pin_mesh", (xw - 0.03, 0.06, wt["top"] + 0.05 - 0.05 + 0.0), (xw + 0.03, 0.06, wt["top"] + 0.0), 0.0025, M["steel"], "stage11", lp)
# 星轮 + 风扇 + 料管
st = empty("star", (dp["x"], -0.0, dp["z"]))
# v3：真正的星轮（6 个半圆齿槽，每槽正好托住一颗珠），v2 是六棱柱，看不出"一格放一颗"
sw = cyl("star_wheel", (dp["x"], 0.0, dp["z"]), 0.040, 0.012, "y", M["brass"], 96, 0.0006, "stage11", st)
for i in range(6):   # 6 个半径 9 mm 的齿槽（珠半径 8 mm），槽心在半径 35 mm 处，初始角与物理一致
    a = math.radians(dp["th0"] + 60 * i)
    ct = cyl(f"star_cut{i}", (dp["x"] + 0.035 * math.cos(a), 0.0, dp["z"] + 0.035 * math.sin(a)), 0.009, 0.03, "y", None, 32, 0, "stage11", st)   # 刀具随星轮一起转
    ct.hide_render = True; ct.hide_viewport = True
    bm_ = sw.modifiers.new(f"pocket{i}", "BOOLEAN"); bm_.operation = 'DIFFERENCE'; bm_.object = ct; bm_.solver = 'EXACT'
if "bevel" in sw.modifiers: sw.modifiers.move(list(sw.modifiers).index(sw.modifiers["bevel"]), len(sw.modifiers) - 1)

cyl("star_hub", (dp["x"], -0.008, dp["z"]), 0.008, 0.006, "y", M["steel"], 24, 0.0005, "stage11", st)
# 护板：贴着星轮右上 1/4 圆，挡住齿槽里的珠子，齿槽转过 0° 才放珠；料管口在正上方
me = bpy.data.meshes.new("star_guard"); bm = bmesh.new(); arc = [math.radians(a_) for a_ in np.linspace(1, 72, 22)]
ring = [(0.0455 * math.cos(a_), 0.0455 * math.sin(a_)) for a_ in arc] + [(0.0475 * math.cos(a_), 0.0475 * math.sin(a_)) for a_ in reversed(arc)]
vb = [bm.verts.new((x, -0.007, z)) for x, z in ring]; vf = [bm.verts.new((x, 0.007, z)) for x, z in ring]
n_ = len(ring); m_ = len(arc)
for i in range(m_ - 1):   # 正反面用四边形条带（避免凹多边形）
    bm.faces.new((vb[i], vb[i + 1], vb[n_ - 2 - i], vb[n_ - 1 - i])); bm.faces.new((vf[n_ - 1 - i], vf[n_ - 2 - i], vf[i + 1], vf[i]))
for i in range(n_): bm.faces.new((vb[i], vb[(i + 1) % n_], vf[(i + 1) % n_], vf[i]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); bm.to_mesh(me); bm.free()
o = bpy.data.objects.new("star_guard", me); sc.collection.objects.link(o); o.location = (dp["x"], 0.0, dp["z"])
o.data.materials.append(M["brass_pol"]); link(o, "stage11")
fn_ = empty("fan", (dp["x"] + 0.09, 0.0, dp["z"] + 0.06))
for a in (0, math.pi):
    box(f"fan_blade{a:.1f}", (dp["x"] + 0.09 + 0.03 * math.cos(a), -0.01, dp["z"] + 0.06 + 0.03 * math.sin(a)), (0.05, 0.002, 0.018), M["brass_pol"], 0.0005, "stage11", fn_,
        rot=(0, -a, 0))
cyl("fan_hub", (dp["x"] + 0.09, -0.01, dp["z"] + 0.06), 0.006, 0.012, "y", M["steel"], 16, 0, "stage11", fn_)
box("disp_plate", (dp["x"] + 0.045, 0.02, dp["z"] + 0.02), (0.17, 0.006, 0.16), M["walnut_dark"], 0.002, "stage11")
rod("disp_leg", (dp["x"] + 0.045, 0.03, 0), (dp["x"] + 0.045, 0.03, dp["z"] - 0.06), 0.01, M["walnut_dark"], "stage11")
lathe("magazine", [(0.0105, dp["z"] + 0.042), (0.0105, dp["z"] + 0.16)], (dp["x"], 0, 0), M["glass"], 32, "stage11", thick=0.0012)
for mi in range(TL.MARBLES):
    sphere(f"m{mi+1}", (0, 0, 0), rm, M["marble"], "stage12", props=dict(snd="marble", mass=P["masses"]["marble"]))
# 绳子：配重 -> 滑轮（长度随配重变化）
rope1 = cyl("rope_w", (xw + 0.0, 0.06, wt["pulley_z"]), 0.0018, 1.0, "z", M["rope"], 8, 0, "stage11", props=dict(snd="rope"))
me = rope1.data
for v in me.vertices: v.co.z -= 0.5      # 原点移到顶端
rod("rope_drum", (xw - 0.03, 0.06, wt["pulley_z"]), (dp["x"], 0.0, dp["z"]), 0.0018, M["rope"], "stage11")
# ================= ⑫ 水瓶轨道 =================
bt = P["bottles"]
pts = []
for tau in np.linspace(0, 6, 400):
    s = 0.5 * 1.5 * tau ** 2 if tau < 0.3 else bt["s_a"] + 0.45 * (tau - 0.3)
    if s > bt["x1"] - bt["x0"] + 0.002: break
    if s <= bt["s_a"]: dz = -s * math.tan(bt["a_slope"])
    else: dz = -bt["s_a"] * math.tan(bt["a_slope"]) - (s - bt["s_a"]) * math.tan(bt["slope"])
    pts.append((bt["x0"] + s, bt["z0"] + rm + dz - 0.0095 * 0 - rm + 0.0))
def poly_rail(name, pts, y, r, mat):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = 3
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for i, (x, z) in enumerate(pts): sp.points[i].co = (x, y, z, 1)
    o = bpy.data.objects.new(name, cu); sc.collection.objects.link(o); o.data.materials.append(mat); link(o, "stage12"); return o
for sy in (-1, 1):
    o = poly_rail(f"btrack{sy}", [(x, z + rm - 0.0095) for x, z in pts], sy * 0.0055, 0.0025, M["brass_pol"]); o["snd"] = "brass_track"
for i, x in enumerate(np.linspace(bt["x0"] + 0.1, bt["x1"] - 0.02, 7)):
    zz = np.interp(x, [p_[0] for p_ in pts], [p_[1] for p_ in pts]) + rm - 0.0095
    rod(f"btrack_post{i}", (x, -0.012, 0.0), (x, -0.012, zz - 0.003), 0.003, M["brass"], "stage12")
    rod(f"btrack_tie{i}", (x, -0.012, zz - 0.003), (x, 0.008, zz - 0.003), 0.0025, M["brass"], "stage12")
riser_z = None
BMAT = [M["bottle_g"], M["bottle_c"], M["bottle_a"]]
for k, b in enumerate(bt["list"]):
    f = note_f(b["note"]); Hb = 0.30; zb = b["zc"] + 0.006 - Hb
    riser_z = zb if riser_z is None else min(riser_z, zb)
for k, b in enumerate(bt["list"]):
    f = note_f(b["note"]); Hb = b["zc"] + 0.006 - riser_z
    prof = [(0.0, 0.0), (0.036, 0.002), (0.038, 0.01), (0.038, Hb * 0.60), (0.030, Hb * 0.72), (0.014, Hb * 0.82), (0.0125, Hb * 0.97), (0.014, Hb * 0.985), (0.0125, Hb)]
    by = rm + 0.0125 - 0.0012
    o = lathe(f"bottle{k}", prof, (b["x"], by, riser_z), BMAT[k % 3], 48, "stage12", thick=0.0022, props=dict(snd="bottle", note=b["note"]))
    wf = 0.12 + 0.55 * (1174.66 - f) / (1174.66 - 587.33)
    w_ = cyl(f"water{k}", (b["x"], by, riser_z + 0.004 + Hb * 0.6 * wf / 2), 0.0345, Hb * 0.6 * wf, "z", M["water"], 48, 0, "stage12")
    set_parent(bpy.data.objects[f"water{k}"], o)
    hits = [TL.WEIGHT_TAUT + mi * TL.BEAT + (k + 1) * TL.BEAT for mi in range(TL.MARBLES)]
    WOBBLE.append((o.name, hits, math.radians(0.5), 2 * math.pi * 5.0, 0.22, -1))
box("bottle_riser", ((bt["list"][0]["x"] + bt["list"][-1]["x"]) / 2, 0.04, riser_z / 2), (bt["list"][-1]["x"] - bt["list"][0]["x"] + 0.2, 0.12, riser_z),
    M["walnut"], 0.003, "stage12")
# ================= ⑬ 钢管风铃 =================
chx = [c["c"][0] for c in P["chimes"]]
for k, c in enumerate(P["chimes"]):
    f = note_f(c["note"]); ln = 0.10 + 0.14 * (587 / f)
    lathe(f"chime{k}", [(0.011, -ln / 2), (0.011, ln / 2)], (c["c"][0], 0, c["c"][2]), M["steel"], 32, "stage13", thick=0.0012,
          props=dict(snd="chime", note=c["note"]))
    o = bpy.data.objects[f"chime{k}"]; o.rotation_euler = (math.pi / 2, 0, 0)
    for sy in (-1, 1):
        rod(f"chime{k}_str{sy}", (c["c"][0], sy * ln * 0.4, c["c"][2] + 0.011), (c["c"][0], sy * 0.12, c["c"][2] + 0.06), 0.0004, M["string"], "stage13", None, 6)
for sy in (-1, 1):
    rod(f"chime_post{sy}", (np.mean(chx), sy * 0.12, 0), (np.mean(chx), sy * 0.12, P["chimes"][0]["c"][2] + 0.12), 0.006, M["walnut_dark"], "stage13")
# ================= ⑭ 弹射 =================
tcp = P["tcup"]
tcu = empty("tcup", (tcp["x"], 0, tcp["z"]))
lathe("tcup_mesh", [(0.0, tcp["z"] - 0.002), (0.022, tcp["z"]), (0.026, tcp["z"] + 0.03)], (tcp["x"], 0, 0), M["brass"], 48, "stage14", tcu,
      thick=0.002, props=dict(snd="brass_cup", note="D4"))
rod("tcup_stem", (tcp["x"], 0, tcp["z"] - 0.002), (tcp["x"], 0, 0.03), 0.004, M["steel"], "stage14", tcu)
cyl("tcup_dashpot", (tcp["x"], 0, 0.02), 0.012, 0.04, "z", M["brass"], 32, 0.001, "stage14")
rod("tcup_trigger", (tcp["x"], 0, 0.045), (P["catapult"]["pivot"][0] - 0.12, 0, 0.05), 0.002, M["brass"], "stage14")
ca = P["catapult"]; cpx, cpz = ca["pivot"]
box("cat_base", (cpx - 0.08, 0, 0.03), (0.32, 0.12, 0.06), M["walnut"], 0.003, "stage14")
for sy in (-1, 1):
    box(f"cat_cheek{sy}", (cpx, sy * 0.03, cpz / 2 + 0.03), (0.05, 0.012, cpz), M["walnut_dark"], 0.002, "stage14")
ar = empty("arm", (cpx, 0, cpz))
box("arm_mesh", (cpx + ca["R"] / 2, 0, cpz), (ca["R"] + 0.03, 0.022, 0.016), M["maple"], 0.002, "stage14", ar)
lathe("arm_spoon", [(0.0, cpz - 0.006), (0.018, cpz - 0.008), (0.021, cpz - 0.02)], (cpx + ca["R"], 0, 0), M["brass"], 32, "stage14", ar, thick=0.002)   # 静止姿态下勺口朝 -z，转到 180° 附近时朝上
a1 = ca["a1"]; stp = (cpx + 0.5 * ca["R"] * math.cos(a1) + 0.019 * math.sin(a1), cpz + 0.5 * ca["R"] * math.sin(a1) - 0.019 * math.cos(a1))
box("arm_stop", (stp[0], 0.0, stp[1]), (0.02, 0.05, 0.02), M["felt"], 0.002, "stage14", rot=(0, -a1, 0), props=dict(snd="felt"))
rod("arm_stop_post", (stp[0], 0.03, 0.06), (stp[0], 0.03, stp[1]), 0.005, M["walnut_dark"], "stage14")
# 弹簧（螺旋）
cu = bpy.data.curves.new("spring", "CURVE"); cu.dimensions = '3D'; cu.bevel_depth = 0.0018
sp = cu.splines.new('POLY'); n = 160; sp.points.add(n - 1)
s0 = Vector((cpx - 0.16, 0, 0.06)); s1 = Vector((cpx - 0.03, 0, cpz - 0.01))
ax = (s1 - s0); axn = ax.normalized(); perp = Vector((0, 1, 0)); perp2 = axn.cross(perp)
for i in range(n):
    u = i / (n - 1); a = u * 12 * 2 * math.pi
    q = s0 + ax * u + perp * 0.012 * math.cos(a) + perp2 * 0.012 * math.sin(a)
    sp.points[i].co = (*q, 1)
so = bpy.data.objects.new("spring", cu); sc.collection.objects.link(so); so.data.materials.append(M["blued"]); link(so, "stage14")
sphere("ball2", (0, 0, 0), P["r_brass"], M["brass_pol"], "stage14", props=dict(snd="brass_ball", mass=0.11))
# ================= ⑮ 漏斗 =================
fu = P["funnel"]; fcx, fcy = fu["c"]
prof = []
for r_ in np.geomspace(0.042, fu["R0"] + 0.01, 60):
    prof.append((r_, fu["z_rim"] - fu["k"] * (1 / r_ - 1 / fu["R0"])))
lathe("funnel", prof, (fcx, fcy, 0), M["copper_spun"], 96, "stage15", thick=0.003, props=dict(snd="copper"))
lathe("funnel_lip", [(fu["R0"] + 0.008, fu["z_rim"] - 0.004), (fu["R0"] + 0.014, fu["z_rim"] + 0.002)], (fcx, fcy, 0), M["brass"], 96, "stage15", thick=0.004)
for i in range(3):
    a = 2 * math.pi * i / 3 + 0.5
    rod(f"funnel_leg{i}", (fcx + 0.26 * math.cos(a), fcy + 0.26 * math.sin(a), 0), (fcx + 0.24 * math.cos(a), fcy + 0.24 * math.sin(a), fu["z_rim"] - 0.01), 0.006, M["iron"], "stage15")
# 接球槽（铜半管）
land = TR["ball2"]; tl = np.array(land["t"]); Lb = np.array(land["loc"])
i0 = np.searchsorted(tl, TL.LAND); i1 = np.searchsorted(tl, TL.FUNNEL_IN)
cpts = Lb[i0:i1 + 1:4]
cu = bpy.data.curves.new("chute", "CURVE"); cu.dimensions = '3D'; cu.bevel_depth = 0.022; cu.bevel_resolution = 4
cu.use_fill_caps = False
sp = cu.splines.new('POLY'); sp.points.add(len(cpts) + 1)
pre = cpts[0] + (cpts[0] - cpts[1]) / np.linalg.norm(cpts[0] - cpts[1]) * 0.08
for i, q in enumerate([pre] + list(cpts) + [cpts[-1] + np.array([0.02, 0, -0.003])]):
    sp.points[i].co = (q[0], q[1], q[2] - P["r_brass"] - 0.022 + 0.022 * 0.3 + 0.0, 1)
cu.fill_mode = 'HALF'
ch = bpy.data.objects.new("chute", cu); sc.collection.objects.link(ch); ch.data.materials.append(M["copper"]); link(ch, "stage15"); ch["snd"] = "copper"
ch.modifiers.new("solid", "SOLIDIFY").thickness = 0.002
# ================= ⑯ 敲钟 =================
be = P["bell"]; bx, by_ = be["x"], be["y"]
Rb = be["R"]; zc = be["zc"]
bprof = [(Rb, zc - 0.10), (Rb * 0.97, zc - 0.085), (Rb * 0.82, zc - 0.05), (Rb * 0.70, zc + 0.0), (Rb * 0.64, zc + 0.05), (Rb * 0.55, zc + 0.085), (Rb * 0.3, zc + 0.1), (0.0, zc + 0.102)]
bp = empty("bell", (bx, by_, zc + 0.13))
lathe("bell_mesh", bprof, (bx, by_, 0), M["brass"], 96, "stage16", bp, thick=0.008, props=dict(snd="bell", note="D3"))
cyl("bell_crown", (bx, by_, zc + 0.115), 0.012, 0.03, "z", M["brass"], 24, 0.001, "stage16", bp)
gal_z = zc + 0.14
for sy in (-1, 1):
    box(f"gallows{sy}", (bx, by_ + sy * 0.16, gal_z / 2), (0.04, 0.04, gal_z + 0.02), M["walnut"], 0.003, "stage16")
box("gallows_top", (bx, by_, gal_z + 0.01), (0.05, 0.36, 0.04), M["walnut"], 0.003, "stage16")
hp = be["hammer_pivot"]
hm = empty("hammer", (hp[0], by_, hp[1]))
rod("hammer_rod", (hp[0], by_, hp[1]), (hp[0], by_, hp[1] - be["Lh"]), 0.003, M["walnut_dark"], "stage16", hm)
cyl("hammer_head", (hp[0], by_, hp[1] - be["Lh"]), be["head_r"], 0.05, "y", M["felt"], 32, 0.002, "stage16", hm, props=dict(snd="felt"))
rod("hammer_post", (hp[0] - 0.03, by_ - 0.05, 0), (hp[0] - 0.03, by_ - 0.05, hp[1] + 0.02), 0.007, M["walnut_dark"], "stage16")
rod("hammer_axle", (hp[0] - 0.03, by_ - 0.05, hp[1]), (hp[0], by_ + 0.02, hp[1]), 0.003, M["steel"], "stage16")
box("hammer_stop", (hp[0] - be["Lh"] * math.sin(math.radians(9)) - 0.03, by_, hp[1] - be["Lh"] * 0.9), (0.02, 0.04, 0.02), M["felt"], 0.002, "stage16", props=dict(snd="felt"))
t2 = P["trig2"]
tg = empty("trigger2", (t2["x"] - 0.03, t2["y"], t2["z"]))
box("trigger2_plate", (t2["x"], t2["y"], t2["z"] - 0.002), (0.07, 0.04, 0.004), M["brass"], 0.0006, "stage16", tg, props=dict(snd="brass"))
box("trigger2_post", (t2["x"] - 0.03, t2["y"], t2["z"] / 2), (0.012, 0.03, t2["z"]), M["walnut_dark"], 0.001, "stage16")
rod("trigger2_link", (t2["x"] + 0.03, t2["y"], t2["z"]), (hp[0] - be["Lh"] * math.sin(math.radians(60)), by_, hp[1] - be["Lh"] * math.cos(math.radians(60)) + 0.02), 0.0012, M["brass"], "stage16")
# ================= ⑰ 收尾 =================
ec = P["endcup"]
bx0 = t2["x"] + 0.02; bx1 = ec["edge_x"]   # 跑道末端即钢球滚出点，紧贴木杯外壁
box("runway", ((bx0 - 0.2 + bx1) / 2, ec["y"], ec["board_z"] / 2), (bx1 - bx0 + 0.2, 0.05, ec["board_z"]), M["walnut"], 0.002, "stage17", props=dict(snd="walnut"))
# v3：木杯嵌进台面的圆孔里（下沉 ec["sink"]），杯沿低于跑道面，镜头能看到杯口、看清钢球是从跑道末端掉进去的
lathe("endcup", [(0.0, 0.0), (0.03, 0.0), (0.034, 0.01), (0.034, ec["z"] + 0.035)], (ec["x"], ec["y"], -ec["sink"]), M["walnut_dark"], 48, "stage17", cap_bottom=False,
      thick=0.004, props=dict(snd="wood_cup", note="D4"))
cyl("endcup_floor", (ec["x"], ec["y"], 0.006 - ec["sink"]), 0.03, 0.012, "z", M["walnut_dark"], 48, 0.001, "stage17")
_hole = cyl("endcup_hole_cutter", (ec["x"], ec["y"], -0.02), 0.0355, 0.06, "z", M["walnut_dark"], 48, 0, "stage17")
_hole = bpy.data.objects["endcup_hole_cutter"]; _hole.hide_render = True; _hole.hide_viewport = True
_bm = bpy.data.objects["bench_top"].modifiers.new("endcup_hole", "BOOLEAN"); _bm.operation = 'DIFFERENCE'; _bm.object = _hole; _bm.solver = 'EXACT'

sphere("ball1", (0, 0, 0), r1, M["steel_ball"], "stage1", props=dict(snd="steel_ball", mass=0.064))
sphere("marble0", (0, 0, 0), rm, M["marble"], "stage8", props=dict(snd="marble", mass=P["masses"]["marble"]))

# ================= 动画写入 =================
def apply_track(name, tr):
    o = bpy.data.objects[name]
    frames = [fr(t) for t in tr["t"]]
    ch = {}
    if "loc" in tr:
        Lc_ = np.array(tr["loc"])
        if o.type == 'EMPTY' and o.children and tr["kind"] == "loc":
            pass
        for i in range(3): ch[("location", i)] = list(Lc_[:, i])
    if "quat" in tr:
        o.rotation_mode = 'QUATERNION'; Q = np.array(tr["quat"])
        for i in range(4): ch[("rotation_quaternion", i)] = list(Q[:, i])
    if "roty" in tr:
        ch[("rotation_euler", 1)] = list(tr["roty"])
    key_channels(o, frames, ch)
for name, tr in TR.items():
    if name in bpy.data.objects: apply_track(name, tr)
    else: print("WARN no object for track", name)
# 被撞物的阻尼摆动（玻璃管绕吊点、水瓶绕瓶底）：多次撞击线性叠加
for name, hits, A, w, tau_d, sgn in WOBBLE:
    o = bpy.data.objects[name]; o.rotation_mode = 'XYZ'
    ts_ = sorted(set([0.0, TL.END] + [h + d for h in hits for d in np.arange(0, 5 * tau_d, 1 / 96)] + hits))
    ts_ = [x for x in ts_ if 0 <= x <= TL.END]
    def ang(t):
        return sum(sgn * A * math.exp(-(t - h) / tau_d) * math.sin(w * (t - h)) for h in hits if t >= h)
    key_channels(o, [fr(t) for t in ts_], {("rotation_euler", 0): [ang(t) for t in ts_]})
# 绳长随配重
wt_tr = TR["weight"]; wz = np.array(wt_tr["loc"])[:, 2]
key_channels(bpy.data.objects["rope_w"], [fr(t) for t in wt_tr["t"]], {("scale", 2): list(wt["pulley_z"] - (wz + 0.125))})
# 骨牌：Bullet 120 Hz 结果
ts = sim["t"]; SL = sim["loc"]; SQ = sim["quat"]
for j, o in enumerate(doms):
    frames = [1.0] + [fr(t) for t in ts] + [float(TL.FRAMES)]
    Lj = np.vstack([SL[0, j], SL[:, j], SL[-1, j]]); Qj = np.vstack([SQ[0, j], SQ[:, j], SQ[-1, j]])
    # 去掉静止段的冗余关键帧
    keep = [0]
    for i in range(1, len(frames) - 1):
        if np.abs(Lj[i] - Lj[keep[-1]]).max() > 1e-6 or np.abs(Qj[i] - Qj[keep[-1]]).max() > 1e-6 or np.abs(Lj[i + 1] - Lj[i]).max() > 1e-6:
            keep.append(i)
    keep.append(len(frames) - 1)
    ch = {("location", i): list(Lj[keep, i]) for i in range(3)}
    ch.update({("rotation_quaternion", i): list(Qj[keep, i]) for i in range(4)})
    key_channels(o, [frames[k] for k in keep], ch)

exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_camera_lights.py")).read())

os.makedirs(os.path.join(ROOT, "blend"), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "blend", "重力乐园.blend"), compress=True)
print("BUILD_OK objects=%d" % len(bpy.data.objects))
