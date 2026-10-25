# 重力乐园 · bpy 建模/材质/动画工具函数
import bpy, bmesh, math, os
from mathutils import Vector, Matrix, Quaternion
from bpy_extras import anim_utils

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = os.path.join(ROOT, "assets", "tex")
COLL = {}

def coll(name):
    if name not in COLL:
        c = bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c); COLL[name] = c
    return COLL[name]

def link(o, c="props"):
    for uc in o.users_collection: uc.objects.unlink(o)
    coll(c).objects.link(o); return o

# ---------------- 材质 ----------------
MATS = {}
def _p(m):
    m.use_nodes = True; return m.node_tree, m.node_tree.nodes["Principled BSDF"]

def _noise_rough(nt, p, lo, hi, scale=60, detail=6):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n = nt.nodes.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = scale; n.inputs["Detail"].default_value = detail
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = lo; mr.inputs["To Max"].default_value = hi
    mr.inputs["From Min"].default_value = 0.3; mr.inputs["From Max"].default_value = 0.7
    nt.links.new(n.outputs["Fac"], mr.inputs["Value"]); nt.links.new(mr.outputs["Result"], p.inputs["Roughness"])
    return tc, n

def _bump(nt, p, tc, scale=300, strength=0.03):
    n = nt.nodes.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = scale; n.inputs["Detail"].default_value = 4
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    b = nt.nodes.new("ShaderNodeBump"); b.inputs["Strength"].default_value = strength; b.inputs["Distance"].default_value = 0.0005
    nt.links.new(n.outputs["Fac"], b.inputs["Height"]); nt.links.new(b.outputs["Normal"], p.inputs["Normal"])

def metal(name, col, lo, hi, tarnish=None, scale=60):
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name); nt, p = _p(m)
    p.inputs["Metallic"].default_value = 1.0
    tc, n = _noise_rough(nt, p, lo, hi, scale)
    if tarnish:
        n2 = nt.nodes.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 9; n2.inputs["Detail"].default_value = 8
        nt.links.new(tc.outputs["Object"], n2.inputs["Vector"])
        cr = nt.nodes.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].position = 0.55; cr.color_ramp.elements[1].position = 0.75
        nt.links.new(n2.outputs["Fac"], cr.inputs["Fac"])
        mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = 'RGBA'
        mx.inputs[6].default_value = (*col, 1); mx.inputs[7].default_value = (*tarnish, 1)
        nt.links.new(cr.outputs["Color"], mx.inputs["Factor"]); nt.links.new(mx.outputs[2], p.inputs["Base Color"])
    else:
        p.inputs["Base Color"].default_value = (*col, 1)
    _bump(nt, p, tc, 400, 0.02)
    MATS[name] = m; return m

def glass(name, col=(0.97, 1, 0.98), rough=0.0, ior=1.5):
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name); nt, p = _p(m)
    p.inputs["Base Color"].default_value = (*col, 1); p.inputs["Roughness"].default_value = rough
    p.inputs["IOR"].default_value = ior; p.inputs["Transmission Weight"].default_value = 1.0
    MATS[name] = m; return m

def dielectric(name, col, rough=0.4, coat=0.0, coat_rough=0.05, sss=0.0, sheen=0.0, scale=40):
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name); nt, p = _p(m)
    p.inputs["Base Color"].default_value = (*col, 1)
    tc, n = _noise_rough(nt, p, rough * 0.8, min(1, rough * 1.25), scale)
    if coat: p.inputs["Coat Weight"].default_value = coat; p.inputs["Coat Roughness"].default_value = coat_rough
    if sss: p.inputs["Subsurface Weight"].default_value = sss; p.inputs["Subsurface Scale"].default_value = 0.003
    if sheen: p.inputs["Sheen Weight"].default_value = sheen; p.inputs["Sheen Roughness"].default_value = 0.5
    MATS[name] = m; return m

def wood(name, tex, scale=1.5, tint=(1, 1, 1), rough_mul=1.0, coat=0.0, nstr=0.6, rot=0.0):
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name); nt, p = _p(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (scale, scale, scale)
    mp.inputs["Rotation"].default_value = (0, 0, rot)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    def img(fn, noncolor=False):
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(os.path.join(TEX, tex, fn), check_existing=True)
        if noncolor: t.image.colorspace_settings.name = "Non-Color"
        t.projection = 'BOX'; t.projection_blend = 0.2
        nt.links.new(mp.outputs["Vector"], t.inputs["Vector"]); return t
    d = img("diff.jpg"); r = img("rough.jpg", True); nn = img("nor.jpg", True)
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs["Factor"].default_value = 1
    nt.links.new(d.outputs["Color"], mul.inputs[6]); mul.inputs[7].default_value = (*tint, 1)
    # v2：颜色微变化（大尺度噪声 ±12%）+ 棱边磨损（Cycles 的 Pointiness：凸起的棱略浅、略粗糙）
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 6.0; nz.inputs["Detail"].default_value = 4.0
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    vr = nt.nodes.new("ShaderNodeMapRange"); vr.inputs["To Min"].default_value = 0.88; vr.inputs["To Max"].default_value = 1.12
    nt.links.new(nz.outputs["Fac"], vr.inputs["Value"])
    mul2 = nt.nodes.new("ShaderNodeMix"); mul2.data_type = 'RGBA'; mul2.blend_type = 'MULTIPLY'; mul2.inputs["Factor"].default_value = 1
    nt.links.new(mul.outputs[2], mul2.inputs[6]); nt.links.new(vr.outputs["Result"], mul2.inputs[7])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    wr = nt.nodes.new("ShaderNodeMapRange"); wr.inputs["From Min"].default_value = 0.52; wr.inputs["From Max"].default_value = 0.62
    wr.inputs["To Min"].default_value = 0.0; wr.inputs["To Max"].default_value = 0.35
    nt.links.new(geo.outputs["Pointiness"], wr.inputs["Value"])
    wear = nt.nodes.new("ShaderNodeMix"); wear.data_type = 'RGBA'; wear.blend_type = 'SCREEN'
    nt.links.new(mul2.outputs[2], wear.inputs[6]); wear.inputs[7].default_value = (0.55, 0.42, 0.30, 1)
    wear.inputs["Factor"].default_value = 0.0
    nt.links.new(mul2.outputs[2], p.inputs["Base Color"])   # Pointiness 在低面数方块上处处偏高，会把整块木头洗白，故不用
    mr = nt.nodes.new("ShaderNodeMath"); mr.operation = 'MULTIPLY'; mr.inputs[1].default_value = rough_mul
    nt.links.new(r.outputs["Color"], mr.inputs[0]); nt.links.new(mr.outputs[0], p.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = nstr
    nt.links.new(nn.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
    if coat: p.inputs["Coat Weight"].default_value = coat; p.inputs["Coat Roughness"].default_value = 0.25
    MATS[name] = m; return m

def emission(name, col, strength):
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name); nt, p = _p(m)
    p.inputs["Base Color"].default_value = (*col, 1)
    p.inputs["Emission Color"].default_value = (*col, 1); p.inputs["Emission Strength"].default_value = strength
    MATS[name] = m; return m

# ---------------- 几何 ----------------
def _finish(o, mat, bevel, smooth, c, parent=None, props=None):
    if mat: o.data.materials.append(mat)
    if bevel:
        b = o.modifiers.new("bevel", "BEVEL"); b.width = bevel; b.segments = 2; b.limit_method = 'ANGLE'
        b.harden_normals = False
    if smooth:
        for pg in o.data.polygons: pg.use_smooth = True
    link(o, c)
    if parent is not None: set_parent(o, parent)
    if props:
        for k, v in props.items(): o[k] = v
    return o

def _new_obj(name, me): o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o); return o

def box(name, center, dims, mat=None, bevel=0.0015, c="props", parent=None, rot=(0, 0, 0), props=None):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * dims[0], v.co.y * dims[1], v.co.z * dims[2]))
    bm.to_mesh(me); bm.free()
    o = _new_obj(name, me); o.location = center; o.rotation_euler = rot
    return _finish(o, mat, bevel, False, c, parent, props)

def cyl(name, center, r, depth, axis="z", mat=None, verts=48, bevel=0.0008, c="props", parent=None, props=None, r2=None):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r if r2 is None else r2, depth=depth)
    bm.to_mesh(me); bm.free()
    o = _new_obj(name, me); o.location = center
    o.rotation_euler = {"z": (0, 0, 0), "x": (0, math.pi / 2, 0), "y": (math.pi / 2, 0, 0)}[axis]
    o = _finish(o, mat, bevel, True, c, parent, props)
    if bevel: o.modifiers["bevel"].limit_method = 'ANGLE'; o.modifiers["bevel"].angle_limit = math.radians(50)
    return o

def sphere(name, center, r, mat=None, c="props", parent=None, segs=48, props=None):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2, radius=r)
    bm.to_mesh(me); bm.free()
    o = _new_obj(name, me); o.location = center
    return _finish(o, mat, 0, True, c, parent, props)

def lathe(name, prof, center, mat=None, segs=64, c="props", parent=None, cap_bottom=False, props=None, thick=None):
    """prof: [(r, z), ...] 从下到上，绕 z 轴旋转"""
    me = bpy.data.meshes.new(name); bm = bmesh.new(); rings = []
    for (r, z) in prof:
        ring = [bm.verts.new((r * math.cos(2 * math.pi * i / segs), r * math.sin(2 * math.pi * i / segs), z)) for i in range(segs)]
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(segs):
            bm.faces.new((a[i], a[(i + 1) % segs], b[(i + 1) % segs], b[i]))
    if cap_bottom: bm.faces.new(list(reversed(rings[0])))
    bm.normal_update(); bm.to_mesh(me); bm.free()
    o = _new_obj(name, me); o.location = center
    if thick:
        s = o.modifiers.new("solid", "SOLIDIFY"); s.thickness = thick; s.offset = 0
    return _finish(o, mat, 0, True, c, parent, props)

def rod(name, p0, p1, r, mat=None, c="props", parent=None, verts=12, props=None):
    p0, p1 = Vector(p0), Vector(p1); d = p1 - p0
    o = cyl(name, (p0 + p1) / 2, r, d.length, "z", mat, verts, 0, c, None, props)
    o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    if parent is not None: set_parent(o, parent)
    return o

def empty(name, loc, c="rigs", parent=None):
    o = bpy.data.objects.new(name, None); o.location = loc; o.empty_display_size = 0.03
    bpy.context.scene.collection.objects.link(o); link(o, c)
    if parent is not None: set_parent(o, parent)
    return o

def set_parent(child, parent):
    bpy.context.view_layer.update()
    mw = child.matrix_world.copy()
    child.parent = parent; child.matrix_parent_inverse = parent.matrix_world.inverted(); child.matrix_world = mw

# ---------------- 动画 ----------------
def _cb(o):
    o.animation_data_create()
    act = bpy.data.actions.new(o.name + "_act"); o.animation_data.action = act
    slot = act.slots.new(id_type=o.id_type, name=o.name); o.animation_data.action_slot = slot
    return anim_utils.action_ensure_channelbag_for_slot(act, slot)

def key_channels(o, frames, chans):
    """chans: {(data_path, index): values}，全部线性插值"""
    cb = _cb(o)
    for (path, idx), vals in chans.items():
        fc = cb.fcurves.new(path, index=idx)
        fc.keyframe_points.add(len(frames))
        co = [0.0] * (2 * len(frames)); co[0::2] = frames; co[1::2] = vals
        fc.keyframe_points.foreach_set("co", co)
        fc.keyframe_points.foreach_set("interpolation", [1] * len(frames))   # 1 = LINEAR
        fc.update()
