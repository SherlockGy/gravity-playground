# 在 -b 模式下启用 Metal GPU（偏好设置不随 .blend 保存，渲染前用 -P scripts/gpu.py 调用）
import bpy
pr = bpy.context.preferences.addons["cycles"].preferences
pr.compute_device_type = "METAL"; pr.get_devices()
for d in pr.devices: d.use = (d.type == "METAL")
bpy.context.scene.cycles.device = "GPU"
print("GPU:", [(d.name, d.type, d.use) for d in pr.devices])
