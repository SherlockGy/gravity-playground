# 从 .blend 里“已烘焙”的动画数据中提取碰撞事件（不读设计时刻），再与设计碰撞日志比对，输出：
#   audio/events/events.json  —— 音频合成唯一的输入（时间、物体、对象、材质、音高、冲量、声像）
#   build/sync_report.md      —— 声画同步精度报告
# 用法: Blender -b blend/重力乐园.blend -P scripts/extract_events.py
# 判据：
#   碰撞/释放/绷紧：动画曲线（线性插值）在某个关键帧处速度突变 |Δv| 明显大于邻域平滑变化（>4×邻域中位数且>下限）
#   节拍器 tick：摆杆角度过零（线性插值求亚帧时刻）
#   骨牌：被撞骨牌的倾角从 0 开始增长的时刻（用起跳后两帧线性外推回 0°，Bullet 120 Hz 数据）
import bpy, os, sys, json, math
import numpy as np
from bpy_extras import anim_utils
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector, Quaternion
ROOT = os.path.dirname(os.path.dirname(bpy.data.filepath))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import timeline as TL
sc = bpy.context.scene; FPS = sc.render.fps; F0 = sc.frame_start
def t_of(f): return (np.asarray(f) - F0) / FPS

def channels(o):
    ad = o.animation_data
    if not ad or not ad.action: return {}
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    out = {}
    for fc in cb.fcurves:
        n = len(fc.keyframe_points); co = np.zeros(2 * n); fc.keyframe_points.foreach_get("co", co)
        out[(fc.data_path, fc.array_index)] = (co[0::2].copy(), co[1::2].copy())
    return out

def signal(o, kind):
    ch = channels(o)
    if kind == "loc":
        ks = [ch[("location", i)] for i in range(3)]
    elif kind == "rot":
        ks = [ch[("rotation_euler", 1)]]
    fr = ks[0][0]
    assert all(len(k[0]) == len(fr) and np.allclose(k[0], fr) for k in ks)
    return t_of(fr), np.stack([k[1] for k in ks], 1)

def jumps(t, X, floor):
    dt = np.diff(t); ok = dt > 1e-6
    V = np.diff(X, axis=0) / np.maximum(dt, 1e-9)[:, None]
    dv = np.full(len(t), 0.0); dvv = np.zeros((len(t), X.shape[1]))
    dvv[1:-1] = V[1:] - V[:-1]; dv[1:-1] = np.linalg.norm(dvv[1:-1], axis=1)
    ev = []
    for i in range(1, len(t) - 1):
        lo, hi = max(1, i - 4), min(len(t) - 1, i + 5)
        nb = np.concatenate([dv[lo:i], dv[i + 1:hi]])
        base = np.median(nb) if len(nb) else 0
        if dv[i] > floor and dv[i] > 4 * base:
            ev.append(dict(t=float(t[i]), dv=float(dv[i]), vin=V[i - 1].tolist(), vout=V[i].tolist()))
    # 非极大抑制（3 ms 内只留最大）
    ev.sort(key=lambda e: -e["dv"]); kept = []
    for e in ev:
        if all(abs(e["t"] - k["t"]) > 0.003 for k in kept): kept.append(e)
    return sorted(kept, key=lambda e: e["t"])

meta = json.load(open(os.path.join(ROOT, "build", "motion.json")))
design = meta["contacts"]; TRK = meta["tracks"]
dsim = json.load(open(os.path.join(ROOT, "build", "domino_sim.json")))
OBJ = bpy.data.objects
extracted = {}   # name -> list of events
# 1) 普通运动体
movers = sorted(set(c[k] for c in design for k in ("a", "b") if c[k] in TRK and not c[k].startswith("dom") and c[k] in OBJ))
for n in movers:
    o = OBJ[n]; kind = "rot" if TRK[n]["kind"] == "rot" else "loc"
    assert o.parent is None or kind == "rot", n
    t, X = signal(o, kind)
    if n == "metro_arm":
        a = X[:, 0]; ev = []
        for i in range(len(t) - 1):
            if a[i] == 0 or (a[i] < 0) != (a[i + 1] < 0):
                if a[i] == 0: tz = t[i]
                elif a[i + 1] == 0: continue
                else: tz = t[i] + (t[i + 1] - t[i]) * a[i] / (a[i] - a[i + 1])
                w = (a[min(i + 1, len(a) - 1)] - a[i]) / max(t[i + 1] - t[i], 1e-9)
                ev.append(dict(t=float(tz), dv=float(abs(w)), rule="zero-crossing"))
        extracted[n] = ev
    else:
        extracted[n] = [dict(e, rule="dv-jump") for e in jumps(t, X, 0.05 if kind == "rot" else 0.03)]
# 2) 骨牌：倾角起始时刻
for i in range(len(dsim["doms"])):
    n = f"dom{i}"; o = OBJ[n]; ch = channels(o)
    fr = ch[("rotation_quaternion", 0)][0]; t = t_of(fr)
    q = np.stack([ch[("rotation_quaternion", k)][1] for k in range(4)], 1)
    q0 = Quaternion(q[0]); ang = np.array([math.degrees(q0.rotation_difference(Quaternion(qq)).angle) for qq in q])
    k = int(np.argmax(ang > 0.3))
    if ang[k] <= 0.3: extracted[n] = []; continue
    # 用 k 与 k+1 两帧线性外推回 0°
    w = (ang[k + 1] - ang[k]) / (t[k + 1] - t[k]); t0 = t[k] - ang[k] / w if w > 0 else t[k]
    t0 = max(t0, t[k - 1] if k > 0 else t0)
    extracted[n] = [dict(t=float(t0), dv=float(math.radians(w)), rule="tilt-onset")]

# 3) 与设计日志匹配。设计里 "domK hit" 表示 domK 被撞（骨牌起倒）；Bullet 记录的接触 domK-1→domK 作为另一个参照
ref = []
for c in design:
    if c["t"] >= TL.END - 1e-6: continue          # 片尾最后一帧之后的事件不计
    if c["a"].startswith("dom") or c["b"].startswith("dom"):
        # 设计日志 "X hit domK"：domK 开始倾倒的时刻就是这次接触
        if c["b"].startswith("dom"):
            tgt = c["b"]; m = [x for x in dsim["contacts"] if x["b"] == tgt]
            ref.append(dict(c, obj=tgt, objs=[tgt], bullet_t=(m[0]["t"] if m else None)))
        else:   # 末块落到扳机板：看扳机板的速度突变
            ref.append(dict(c, obj=c["b"], objs=[c["b"]] if c["b"] in extracted else [c["a"]]))
    else:
        ref.append(dict(c, obj=c["a"], objs=[c["a"]] + ([c["b"]] if c["b"] in extracted else [])))
used = set(); rows = []
for c in ref:
    cand = []
    for o_ in c["objs"]:
        for j, e in enumerate(extracted.get(o_, [])):
            d_ = abs(e["t"] - c["t"])
            if d_ < 0.040 and ((o_, j) not in used or d_ < 0.001): cand.append((d_, o_, j))
    if not cand: rows.append(dict(c, found=False)); continue
    _, o_, j = min(cand); used.add((o_, j)); e = extracted[o_][j]
    rows.append(dict(c, found=True, t_ex=e["t"], dv=e["dv"], rule=e["rule"], via=o_))
extras = [(n, e) for n, evs in extracted.items() for j, e in enumerate(evs) if (n, j) not in used]

# 4) 声像与接触位置（按提取时刻求值场景）
cam = sc.camera
def snd_of(name):
    o = OBJ.get(name)
    if o is None: return name, None
    return o.get("snd", name), o.get("note")
events = []
for r in rows:
    if not r["found"]: continue
    t = r["t_ex"]; f = F0 + t * FPS
    sc.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
    oa = OBJ[r["obj"]]; ob = OBJ.get(r["b"])
    pa = oa.matrix_world.translation.copy()
    pb = ob.matrix_world.translation.copy() if ob else pa
    p = (pa + pb) / 2 if r["kind"] in ("hit", "bounce") else pa
    sv = world_to_camera_view(sc, cam, p)
    dist = (cam.matrix_world.translation - p).length
    ma, na = snd_of(r["obj"]); mb, nb = snd_of(r["b"])
    events.append(dict(t=t, t_design=r["t"], kind=r["kind"], a=r["obj"], b=r["b"], mat_a=ma, mat_b=mb,
                       note=nb if nb else na, dv=r["dv"], mass_a=oa.get("mass"), size_b=(ob.get("size") if ob else None),
                       pos=[round(v, 4) for v in p], pan=float(np.clip(sv.x * 2 - 1, -1.5, 1.5)), depth=float(dist),
                       onscreen=bool(0 <= sv.x <= 1 and 0 <= sv.y <= 1 and sv.z > 0), rule=r["rule"]))
# 滚动段：从动画曲线算速度
rolls = []
for (t0, t1, obj, surf) in meta["rolls"]:
    o = OBJ[obj]; t, X = signal(o, "rot" if TRK.get(obj, {}).get("kind") == "rot" else "loc")
    m = (t >= t0) & (t <= t1)
    if m.sum() < 2: continue
    tt = np.arange(t0, t1, 1 / 240.0)   # 先在均匀网格上重采样（避免相邻关键帧间隔过小导致的数值尖峰）
    Xu = np.stack([np.interp(tt, t, X[:, i]) for i in range(X.shape[1])], 1)
    sp = np.linalg.norm(np.gradient(Xu, tt, axis=0), axis=1) if len(tt) > 2 else np.zeros(len(tt))
    rolls.append(dict(t0=t0, t1=t1, obj=obj, surface=surf, mat=OBJ[surf].get("snd", surf) if surf in OBJ else surf,
                      t=tt.tolist(), speed=sp.tolist()))
os.makedirs(os.path.join(ROOT, "audio", "events"), exist_ok=True)
json.dump(dict(fps=FPS, end=TL.END, events=events, rolls=rolls), open(os.path.join(ROOT, "audio", "events", "events.json"), "w"), indent=1, ensure_ascii=False)

# 5) 报告
found = [r for r in rows if r["found"]]; miss = [r for r in rows if not r["found"]]
res = np.array([(r["t_ex"] - r["t"]) * 1000 for r in found])
dom = [r for r in found if r["obj"].startswith("dom") and r.get("bullet_t")]
resb = np.array([(r["t_ex"] - r["bullet_t"]) * 1000 for r in dom]) if dom else np.zeros(1)
by = {}
for r in found:
    g = "dom" if r["obj"].startswith("dom") else r["obj"]
    by.setdefault(g, []).append((r["t_ex"] - r["t"]) * 1000)
L = ["# 声画同步报告（自动生成：scripts/extract_events.py）", "",
     f"- 设计碰撞日志条目：{len(rows)}；从烘焙动画中提取并匹配：{len(found)}；未找到：{len(miss)}",
     f"- 提取时刻 − 设计时刻：平均 {res.mean():+.2f} ms，|误差| 中位 {np.median(abs(res)):.2f} ms，95% {np.percentile(abs(res),95):.2f} ms，最大 {abs(res).max():.2f} ms",
     f"- 骨牌：倾角起始时刻 − Bullet 接触时刻：平均 {resb.mean():+.2f} ms，最大 |{abs(resb).max():.2f}| ms（Bullet 120 Hz 记录）",
     f"- 未匹配到设计日志的额外速度突变：{len(extras)} 个（不发声，列在下表供检查）",
     "- 音频事件直接使用“提取时刻”，所以音频与画面运动的偏差即为 0（采样量化 1/48000 s ≈ 0.02 ms）；画面每帧 41.7 ms，接触落在两帧之间时由运动模糊呈现。",
     "", "| 机构 | 事件数 | 平均误差 ms | 最大 |误差| ms |", "|---|---|---|---|"]
for g, v in by.items():
    v = np.array(v); L.append(f"| {g} | {len(v)} | {v.mean():+.2f} | {abs(v).max():.2f} |")
if miss:
    L += ["", "## 未找到", ""] + [f"- {r['t']:.4f}s {r['obj']}→{r['b']} ({r['kind']})" for r in miss]
if extras:
    L += ["", "## 额外速度突变（未发声）", ""] + [f"- {e['t']:.4f}s {n} |Δv|={e['dv']:.3f}" for n, e in extras[:80]]
open(os.path.join(ROOT, "build", "sync_report.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L[:9])); print("EXTRACT_OK", len(events), "events")
