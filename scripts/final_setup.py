# 正式渲染设置（Cycles / Metal GPU，1920x1080，PNG 序列，可续渲）。由 resume_render.sh 调用。
import bpy, os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "gpu.py")).read())
sc = bpy.context.scene; r = sc.render; cy = sc.cycles
r.engine = 'CYCLES'; r.resolution_x = 1920; r.resolution_y = 1080; r.resolution_percentage = 100
cy.samples = int(os.environ.get("GL_SAMPLES", "128")); cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.015
cy.use_denoising = True; cy.denoiser = 'OPENIMAGEDENOISE'
r.use_persistent_data = True
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGB'; r.image_settings.color_depth = '8'
r.use_overwrite = False; r.use_placeholder = True
r.filepath = os.path.join(os.path.dirname(os.path.dirname(bpy.data.filepath)), "renders", "final", "frame_")
print("FINAL_SETUP samples", cy.samples, "device", cy.device)
