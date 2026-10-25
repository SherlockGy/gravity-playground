# 沙沙声审计（v2）：把每种音色单独合成一次，过混响，测“尾巴”（起音后 150–600 ms）的
#   ① 4–16 kHz 能量相对起音（dB）  ② 2–16 kHz 频谱平坦度（越接近 1 越像噪声/沙沙，纯音调尾巴 < 0.1）
# 同时对比 v1 的“白噪声混响”，以及开头 0–8 s 的分轨（events / rolls / reverb）
import os, sys, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(ROOT, "scripts", "synth_audio.py")).read()
src = src[:src.index("used = {}")]
g = {"__file__": os.path.join(ROOT, "scripts", "synth_audio.py")}; exec(src, g)
SR = g["SR"]; nf = g["nf"]
ns = {}; exec(open(os.path.join(ROOT, "scripts", "synth_audio.py")).read().split("# ---------- 房间混响")[1].split("hL, hR = ir(1), ir(2)")[0].split("\n", 1)[1], g, ns)
ir_v2 = ns["ir"]; conv = ns["conv"]
def ir_v1(seed):
    gg = np.random.default_rng(seed); n = int(1.6 * SR); t = np.arange(n) / SR
    x = gg.standard_normal(n) * np.exp(-6.9 * t / 1.0)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR); X *= 1 / (1 + (f / 5500) ** 2); X *= np.clip(f / 120, 0, 1)
    y = np.fft.irfft(X, n); y = np.concatenate([np.zeros(int(0.014 * SR)), y]); return y / np.sqrt(np.sum(y ** 2))
VO = {"metronome": g["v_wood_click"](2300, 0.012, 0.7), "flap": g["v_brass_click"](1800, 0.04), "marimba A5": g["v_marimba"](nf("A5"), 1.0),
      "brass cup A3": g["v_cup"](nf("A3"), 1.0), "felt thud": g["v_thud"](95, 0.18), "domino porcelain": g["v_dom"](3, "dom_porcelain"),
      "domino walnut": g["v_dom"](50, "dom_walnut"), "cradle click": g["v_steel_click"](), "glass tube": g["v_glass_tube"](nf("D5"), 1),
      "bowl": g["v_bowl"](nf("A4"), 1), "bottle": g["v_bottle"](nf("A5"), 1), "chime": g["v_chime"](nf("D6"), 1),
      "rope taut": g["v_rope_taut"](), "bell": g["v_bell"](nf("D3")), "wood cup": g["v_wood_click"](nf("D4"), 0.09, 0.6)}
def measure(y):
    n = len(y); Y = np.fft.rfft(y); f = np.fft.rfftfreq(n, 1 / SR)
    hp = np.fft.irfft(Y * ((f > 4000) & (f < 16000)), n)
    a = np.mean(hp[:int(0.02 * SR)] ** 2) + 1e-20; tail = slice(int(0.15 * SR), int(0.6 * SR))
    b = np.mean(hp[tail] ** 2) + 1e-20
    s = y[tail]; S = np.abs(np.fft.rfft(s * np.hanning(len(s)))) ** 2; fs = np.fft.rfftfreq(len(s), 1 / SR); S = S[(fs > 2000) & (fs < 16000)] + 1e-30
    return 10 * np.log10(b / a), float(np.exp(np.mean(np.log(S))) / np.mean(S))
h1, h2 = ir_v1(1), ir_v2(1)
print(f"{'音色':16s} | v1 尾巴高频 dB / 平坦度 | v2 尾巴高频 dB / 平坦度")
worst = 0
for k, y in VO.items():
    y = np.asarray(y, float); y = np.concatenate([y, np.zeros(int(0.7 * SR))])
    m1 = measure(y + 0.22 * conv(y, h1)); m2 = measure(y + 0.16 * conv(y, h2)); worst = max(worst, m2[1])
    print(f"{k:16s} | {m1[0]:7.1f} / {m1[1]:.3f}        | {m2[0]:7.1f} / {m2[1]:.3f}")
print("v2 最大尾巴平坦度", round(worst, 3))
