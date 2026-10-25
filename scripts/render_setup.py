# 通用渲染设置（由 scripts/render.sh 调用，参数走环境变量）。也可以手动：
#   GL_SAMPLES=64 GL_OUT=renders/final Blender -b blend/重力乐园.blend -P scripts/render_setup.py -a
import bpy, os
E = os.environ.get
sc = bpy.context.scene; r = sc.render
root = os.path.dirname(os.path.dirname(bpy.data.filepath))
engine = E("GL_ENGINE", "cycles").lower()
if engine == "cycles":
    exec(open(os.path.join(root, "scripts", "gpu.py")).read())
    cy = sc.cycles; r.engine = 'CYCLES'
    cy.samples = int(E("GL_SAMPLES", "64")); cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.015
    cy.use_denoising = True; cy.denoiser = 'OPENIMAGEDENOISE'
elif engine == "eevee":
    ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    r.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in ids else 'BLENDER_EEVEE_NEXT'
    sc.eevee.taa_render_samples = int(E("GL_SAMPLES", "64"))
    try: sc.eevee.use_raytracing = True
    except Exception: pass
else:
    raise SystemExit("GL_ENGINE 只能是 cycles 或 eevee")
r.resolution_x = 1920; r.resolution_y = 1080; r.resolution_percentage = int(E("GL_PCT", "100"))
mb = E("GL_MBLUR", "auto")
if mb == "off": r.use_motion_blur = False          # 全片关闭运动模糊
else: r.use_motion_blur = True                     # auto：按分镜表逐镜快门（0.08–0.35）
r.use_persistent_data = True
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGB'; r.image_settings.color_depth = '8'
r.use_overwrite = False; r.use_placeholder = True  # 已有的帧跳过；正在渲的帧先写 0 字节占位，防止两个进程重复渲同一帧
sc.frame_start = int(E("GL_START", "1")); sc.frame_end = int(E("GL_END", "1044"))
out = E("GL_OUT", os.path.join(root, "renders", "final"))
if not os.path.isabs(out): out = os.path.join(root, out)
r.filepath = os.path.join(out, "frame_")
print("RENDER_SETUP", engine, "samples", E("GL_SAMPLES", "64"), "pct", r.resolution_percentage, "mblur", mb,
      "frames", sc.frame_start, sc.frame_end, "out", out, "device", getattr(sc.cycles, "device", "-"))
