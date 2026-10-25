# 画质档位测速：Blender -b blend/重力乐园.blend -P scripts/bench_tiers.py -- TIER t1 t2 ...
# TIER: c32 / c64 / c128 / c64fast / c128fast / eevee。每个时刻连续渲两帧（t 与 t+1 帧），取第二帧为稳态耗时（与续渲序列一致，含持久数据）
import bpy, os, sys, time, json
args = sys.argv[sys.argv.index("--") + 1:]; tier = args[0]; ts = [float(a) for a in args[1:]]
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.dirname(here)
sc = bpy.context.scene; r = sc.render
if tier.startswith("c"):
    os.environ["GL_SAMPLES"] = tier[1:].replace("fast", "")
    exec(open(os.path.join(here, "final_setup.py")).read())
    cy = sc.cycles
    if tier.endswith("fast"):
        cy.max_bounces = 8; cy.diffuse_bounces = 2; cy.glossy_bounces = 3
        cy.transmission_bounces = 8; cy.transparent_max_bounces = 8
        cy.caustics_reflective = False; cy.caustics_refractive = False
        cy.blur_glossy = 1.0
else:
    r.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
    r.resolution_x = 1920; r.resolution_y = 1080; r.resolution_percentage = 100
    ee = sc.eevee; ee.taa_render_samples = 64
    try: ee.use_raytracing = True
    except Exception as e: print("no raytracing", e)
r.use_overwrite = True
out = os.path.join(root, "renders", "bench"); os.makedirs(out, exist_ok=True)
res = []
for t in ts:
    f = round(1 + t * r.fps)
    for k, ff in enumerate((f, f + 1)):
        sc.frame_set(ff); r.filepath = os.path.join(out, f"{tier}_{t:05.2f}s{'_warm' if k == 0 else ''}.png")
        t0 = time.time(); bpy.ops.render.render(write_still=True); dt = time.time() - t0
        print("BENCH", tier, t, ff, round(dt, 2))
    res.append(dict(tier=tier, t=t, frame=f + 1, seconds=round(dt, 2)))
jp = os.path.join(root, "build", "bench_tiers.json")
allr = json.load(open(jp)) if os.path.exists(jp) else []
allr = [x for x in allr if not (x["tier"] == tier and x["t"] in ts)] + res
json.dump(allr, open(jp, "w"), indent=1)
