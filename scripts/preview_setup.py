# 预览渲染设置（v2）：Cycles 低采样（与成片同一套材质与光照，EEVEE 下玻璃瓶会发黑），960x540，可续渲
import bpy, os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "gpu.py")).read())
sc = bpy.context.scene; r = sc.render; cy = sc.cycles
r.engine = 'CYCLES'; r.resolution_percentage = 50
cy.samples = 24; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.04
cy.use_denoising = True; cy.denoiser = 'OPENIMAGEDENOISE'; r.use_persistent_data = True
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGB'
r.use_overwrite = False; r.use_placeholder = True
r.filepath = os.path.join(os.path.dirname(os.path.dirname(bpy.data.filepath)), "renders", "preview", "frames_v2", "p_")
