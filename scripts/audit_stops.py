# 急停审计：在 build/motion.json 的每条轨迹里找“运动中的物体在一个关键帧内几乎停住”的地方
# 判据：前一段速度 > 阈值，后一段速度 < 前一段的 15%；列出是否有设计接触与之对应（有接触也可能是“撞上去死停”，需要人工判断）
import json, os, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(ROOT, "build", "motion.json"))); C = d["contacts"]
out = []
for n, tr in d["tracks"].items():
    t = np.array(tr["t"]); dt = np.diff(t)
    for key, thr in (("loc", 0.05), ("roty", 0.5)):
        if key not in tr: continue
        X = np.array(tr[key]); X = X[:, None] if X.ndim == 1 else X
        V = np.linalg.norm(np.diff(X, axis=0), axis=1) / np.maximum(dt, 1e-9)
        for i in range(1, len(V)):
            if V[i - 1] > thr and V[i] < 0.15 * V[i - 1] and dt[i] > 1e-4:
                # 后续 0.15 s 内是否一直几乎不动（真正的“定住”）
                j = i; tt = t[i]
                while j < len(V) and t[j] < tt + 0.15: j += 1
                still = np.all(V[i:j] < 0.15 * V[i - 1])
                c = [x for x in C if (x["a"] == n or x["b"] == n) and abs(x["t"] - tt) < 0.006]
                if still: out.append((round(float(tt), 4), n, key, round(float(V[i - 1]), 3), [f'{x["a"]}->{x["b"]}' for x in c]))
for o in sorted(out): print(o)
print("STOPS", len(out))
