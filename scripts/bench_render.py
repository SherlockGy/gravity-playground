# 重力乐园 · 渲染/物理基准测试（设计阶段用，非成片场景）
# 用法: Blender -b --factory-startup -P scripts/bench_render.py -- <mode>
# mode: physics | cycles | eevee
import bpy, sys, time, math, json, os
from mathutils import Vector

mode = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "cycles"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "renders", "bench")
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = 'METRIC'

def mat(name, base, metal=0.0, rough=0.5, trans=0.0, ior=1.45, noise=True):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*base, 1)
    p.inputs["Metallic"].default_value = metal
    p.inputs["Roughness"].default_value = rough
    p.inputs["IOR"].default_value = ior
    if "Transmission Weight" in p.inputs: p.inputs["Transmission Weight"].default_value = trans
    if noise:  # 粗糙度变化，模拟磨损/指纹
        n = nt.nodes.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = 40
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value = rough*0.7; mr.inputs["To Max"].default_value = min(1, rough*1.4)
        nt.links.new(n.outputs["Fac"], mr.inputs["Value"]); nt.links.new(mr.outputs["Result"], p.inputs["Roughness"])
        b = nt.nodes.new("ShaderNodeBevel"); b.inputs["Radius"].default_value = 0.002
        nt.links.new(b.outputs["Normal"], p.inputs["Normal"])
    return m

wood = mat("wood", (0.45, 0.28, 0.15), rough=0.55)
brass = mat("brass", (0.95, 0.72, 0.38), metal=1, rough=0.25)
steel = mat("steel", (0.8, 0.8, 0.82), metal=1, rough=0.15)
glass = mat("glass", (1, 1, 1), rough=0.02, trans=1.0, ior=1.5, noise=False)
ceramic = mat("ceramic", (0.9, 0.88, 0.82), rough=0.2)

bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.025)); floor = bpy.context.object  # 5cm 厚台面，顶面 z=0
floor.scale = (4, 4, 0.05); bpy.ops.object.transform_apply(location=False, rotation=False, scale=True); floor.data.materials.append(wood)
doms = []
for i in range(30):  # 1:1 真实尺度: 骨牌 48x24x8 mm
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.6 + i*0.032, 0, 0.024))
    d = bpy.context.object; d.scale = (0.008, 0.024, 0.048); bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bm = d.modifiers.new("bev", "BEVEL"); bm.width = 0.0012; bm.segments = 3
    d.data.materials.append([wood, ceramic, brass][i % 3]); doms.append(d)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.012, location=(-0.64, 0, 0.06), segments=48, ring_count=24)
ball = bpy.context.object; ball.data.materials.append(steel); bpy.ops.object.shade_smooth()
bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.12, location=(0.45, 0.06, 0.06), vertices=64)
g = bpy.context.object; g.data.materials.append(glass); bpy.ops.object.shade_smooth()
for k, (x, n) in enumerate([(0.3, 6)]):
    for j in range(n):  # 黄铜音条
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0.25 + j*0.04, -0.08, 0.01))
        b = bpy.context.object; b.scale = (0.012, 0.16 - j*0.015, 0.006); b.data.materials.append(brass)

# 灯光: 主光 + 轮廓光 + 环境
for loc, en, sz in [((-0.8, -1.0, 1.2), 120, 0.8), ((1.0, 1.0, 0.6), 60, 0.4)]:
    bpy.ops.object.light_add(type='AREA', location=loc); L = bpy.context.object
    L.data.energy = en; L.data.size = sz
    L.rotation_euler = (Vector((0, 0, 0.05)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.055, 0.06, 1)

bpy.ops.object.camera_add(location=(0.05, -0.55, 0.16)); cam = bpy.context.object; sc.camera = cam
cam.rotation_euler = (Vector((0.0, 0, 0.03)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 50; cam.data.dof.use_dof = True; cam.data.dof.focus_distance = 0.55; cam.data.dof.aperture_fstop = 4.0

r = sc.render; r.resolution_x, r.resolution_y, r.resolution_percentage = 1920, 1080, 100
res = {"mode": mode}

if mode == "physics":
    bpy.ops.rigidbody.world_add(); rw = sc.rigidbody_world
    rw.substeps_per_frame = 20; rw.solver_iterations = 30
    sc.frame_start, sc.frame_end = 1, 150; rw.point_cache.frame_end = 150
    sc.render.fps = 30
    for d in doms:
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = d; d.select_set(True)
        bpy.ops.rigidbody.object_add(); d.rigid_body.mass = 0.012; d.rigid_body.friction = 0.4
        d.rigid_body.restitution = 0.2; d.rigid_body.collision_shape = 'BOX'
        d.rigid_body.use_margin = True; d.rigid_body.collision_margin = 0.0005
    bpy.ops.object.select_all(action='DESELECT'); floor.select_set(True)
    bpy.context.view_layer.objects.active = floor; bpy.ops.rigidbody.object_add(); floor.rigid_body.type = 'PASSIVE'
    floor.rigid_body.collision_shape = 'BOX'  # 平面必须用 BOX，否则零厚度会穿透
    floor.rigid_body.use_margin = True; floor.rigid_body.collision_margin = 0.0005  # 默认 0.04m 边距对 48mm 骨牌过大
    S = float(os.environ.get("GL_SCALE", "1"))  # 整体放大倍数；重力同步放大以保持真实时序
    if S != 1:
        for o in sc.objects:
            if o.type == 'MESH':
                o.location *= S; o.scale *= S
        bpy.context.view_layer.update()
        sc.gravity = (0, 0, -9.81 * S)
        for d in doms: d.rigid_body.collision_margin = 0.0005 * S
        floor.rigid_body.collision_margin = 0.0005 * S
    res["scale"] = S
    th = math.radians(15); c, s_ = math.cos(th), math.sin(th)  # 绕底部前棱倾斜第一张，避免初始穿插
    x0 = doms[0].location.x
    doms[0].location = (x0 + 0.004 + (-0.004*c + 0.024*s_), 0, 0.0005 + 0.004*s_ + 0.024*c)
    doms[0].rotation_euler = (0, th, 0)
    for d in doms[1:]: d.location.z += 0.0005
    t = time.time()
    fallen = []
    tip = {}
    for f in range(1, 151):
        sc.frame_set(f)
        if f in (1, 10, 30): res[f"z10_f{f}"] = round(doms[10].matrix_world.translation.z, 4)
        for i, d in enumerate(doms):
            if i not in tip and abs(d.matrix_world.to_euler().y) > math.radians(45): tip[i] = f
    res["rbw_objs"] = len(rw.collection.objects) if rw.collection else None
    res["floor_rb"] = (floor.rigid_body.type, floor.rigid_body.collision_shape, floor.rigid_body.collision_margin) if floor.rigid_body else None
    res["dims_floor"] = list(floor.dimensions)
    res["tip_frames"] = [tip.get(i) for i in range(0, 30, 3)]
    res["sim_150f_s"] = round(time.time() - t, 2)
    res["times"] = {}
    res["fallen"] = sum(1 for d in doms if abs(d.matrix_world.to_euler().y) > 0.6)
    res["last_pos"] = [round(v, 5) for v in doms[-1].matrix_world.translation]
elif mode == "cycles":
    r.engine = 'CYCLES'; cy = sc.cycles
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = 'METAL'; prefs.get_devices()
    for dv in prefs.devices: dv.use = (dv.type == 'METAL')
    res["devices"] = [(dv.name, dv.type, dv.use) for dv in prefs.devices]
    cy.device = 'GPU'; cy.use_denoising = True; cy.denoiser = 'OPENIMAGEDENOISE'
    cy.use_adaptive_sampling = True
    for spp in (64, 128, 256):
        cy.samples = spp; r.filepath = f"{OUT}/cycles_{spp}spp.png"
        t = time.time(); bpy.ops.render.render(write_still=True); res[f"cycles_{spp}spp_s"] = round(time.time() - t, 2)
elif mode == "eevee":
    names = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    r.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in names else 'BLENDER_EEVEE'
    ee = sc.eevee
    try: ee.use_raytracing = True
    except Exception as e: res["rt_err"] = str(e)
    ee.taa_render_samples = 64
    r.filepath = f"{OUT}/eevee_64.png"
    for k in range(2):
        t = time.time(); bpy.ops.render.render(write_still=True); res[f"eevee_run{k}_s"] = round(time.time() - t, 2)
print("BENCH_RESULT " + json.dumps(res))
