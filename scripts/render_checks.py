# 快速检查帧：EEVEE 低分辨率渲染若干时刻。用法: Blender -b blend/重力乐园.blend -P scripts/render_checks.py -- 1.0 3.5 ...
import bpy, sys, os
argv = sys.argv[sys.argv.index("--") + 1:]
pct = 33; eng = 'BLENDER_EEVEE'
if argv and argv[0].startswith("pct="): pct = int(argv.pop(0)[4:])
if argv and argv[0] == "cycles": eng = 'CYCLES'; argv.pop(0)
sc = bpy.context.scene; r = sc.render; r.engine = eng; r.resolution_percentage = pct
if eng == 'CYCLES':
    exec(open(os.path.join(os.path.dirname(__file__), 'gpu.py')).read()); sc.cycles.samples = 32
out = os.path.join(os.path.dirname(bpy.data.filepath), "..", "renders", "preview", "check")
os.makedirs(out, exist_ok=True)
for a in argv:
    t = float(a); f = 1 + t * sc.render.fps
    sc.frame_set(int(f), subframe=f - int(f))
    r.filepath = os.path.join(out, f"t{t:05.2f}.png"); bpy.ops.render.render(write_still=True)
print("CHECK_DONE")
