# 满质量 Cycles 静帧（与正式渲染同一设置）并记录每帧耗时 -> renders/preview/stills/, build/cycles_timing.json
import bpy, os, sys, time, json
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "final_setup.py")).read())
sc = bpy.context.scene; r = sc.render; root = os.path.dirname(os.path.dirname(bpy.data.filepath))
out = os.path.join(root, "renders", "preview", "stills"); os.makedirs(out, exist_ok=True)
res = []
for a in sys.argv[sys.argv.index("--") + 1:]:
    t = float(a); f = round(1 + t * sc.render.fps); sc.frame_set(f)
    r.filepath = os.path.join(out, f"cycles_{t:05.2f}s_f{f:04d}.png")
    t0 = time.time(); bpy.ops.render.render(write_still=True); dt = time.time() - t0
    res.append(dict(t=t, frame=f, seconds=round(dt, 1))); print("STILL", t, f, round(dt, 1))
json.dump(res, open(os.path.join(root, "build", "cycles_timing.json"), "w"), indent=1)
