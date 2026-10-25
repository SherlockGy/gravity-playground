# 重力乐园 · 节奏/音色小样 v0（设计阶段，只用于听节奏和音高设计，不是成片音频）
# 全部为程序合成（模态合成：每个物体 = 若干衰减正弦 + 激励噪声），无采样。
# 运行: <Blender 自带 python3.13> scripts/sketch_audio.py  -> audio/sketch/节奏小样_v0.wav
import wave, os, numpy as np
from timeline import events, NOTE, END

SR = 48000
rng = np.random.default_rng(7)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "audio", "sketch"); os.makedirs(OUT, exist_ok=True)

def env_t(d): return np.arange(int(d * SR)) / SR

def modal(f0, ratios, decays, amps, dur, click=0.0, click_lp=6000):
    tt = env_t(dur); y = np.zeros_like(tt)
    for r, d, a in zip(ratios, decays, amps):
        f = f0 * r
        if f < SR / 2.2:
            y += a * np.sin(2 * np.pi * f * tt + rng.uniform(0, 6.28)) * np.exp(-tt / d)
    if click:
        n = int(0.004 * SR); c = rng.standard_normal(n) * np.exp(-np.arange(n) / (0.0008 * SR))
        y[:n] += click * bandlimit(c, 200, click_lp)
    a = int(0.0015 * SR); y[:a] *= np.linspace(0, 1, a)   # 接触时间 ~1.5ms
    return y

def bandlimit(x, lo, hi):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] = 0; return np.fft.irfft(X, len(x))

def noise(dur, lo, hi): return bandlimit(rng.standard_normal(int(dur * SR)), lo, hi)

def synth(e):
    k = e["kind"]; f = NOTE.get(e.get("note", ""), 440.0)
    if k == "woodblock": return modal(f, [1, 2.57, 4.1], [0.05, 0.02, 0.01], [1, .4, .2], .3, click=.6)
    if k == "ratchet":   return modal(4200, [1, 1.7, 2.9], [.006, .004, .003], [1, .6, .4], .05, click=1)
    if k in ("tink", "pan"): return modal(f, [1, 2.76, 5.4], [.5, .15, .05], [1, .35, .15], 1.6, click=.3)
    if k == "rosewood":  return modal(f, [1, 3.0, 6.0], [.45, .12, .04], [1, .3, .08], 1.5, click=.5, click_lp=4000)   # 木琴音条调为 1:3
    if k == "brasscup":  return modal(f, [1, 2.32, 3.9, 5.1], [.9, .5, .3, .2], [1, .6, .4, .25], 2.5, click=.4)
    if k == "latch":     return modal(2600, [1, 1.9, 3.3], [.015, .01, .006], [1, .5, .3], .12, click=1)
    if k == "domino":
        u = e["size"]; f0 = 1500 - 900 * u
        return modal(f0, [1, 2.3, 3.7], [.02 + .03 * u, .01, .006], [1, .5, .3], .25, click=.8, click_lp=7000 - 3000 * u)
    if k == "bigblock":  return modal(160, [1, 2.4, 4.3], [.12, .06, .03], [1, .5, .3], .8, click=.8, click_lp=2500) + np.pad(noise(.15, 40, 400) * np.exp(-env_t(.15) / .04), (0, int(.65 * SR)))
    if k == "cradle":    return modal(3800, [1, 1.53, 2.31], [.03, .02, .012], [1, .6, .4], .2, click=.7, click_lp=12000)
    if k == "glass":     return modal(f, [1, 2.32, 4.25, 6.63], [1.4, .6, .3, .15], [1, .3, .15, .06], 3.0, click=.15)
    if k == "ceramic":   return modal(f, [1, 2.6, 4.9, 7.6], [.7, .3, .12, .06], [1, .4, .2, .1], 2.0, click=.3)
    if k == "bottle":    return modal(f, [1, 2.08, 3.5, 5.3], [1.0, .45, .2, .1], [1, .25, .12, .05], 2.4, click=.2)
    if k == "chime":     return modal(f, [1, 2.0, 3.01, 4.1, 5.4], [2.2, 1.6, 1.0, .5, .3], [.5, 1, .7, .3, .15], 4.0, click=.2)
    if k == "bell":      # 小三度钟的分音: hum .5, prime 1, tierce 1.2, quint 1.5, nominal 2 ...
        y = modal(f, [.5, 1, 1.2, 1.5, 2, 2.5, 3, 4.2], [7, 5, 4, 3, 3.5, 2, 1.5, .8], [.8, .7, .6, .3, 1, .4, .3, .2], 8.0, click=.4)
        y += 0.5 * modal(f * 1.003, [.5, 1, 2], [7, 5, 3.5], [.6, .5, .7], 8.0)   # 轻微拍频
        return y
    if k == "tok":       return modal(f, [1, 2.7, 4.6], [.08, .03, .015], [1, .4, .2], .4, click=.6, click_lp=3000)
    if k == "thud":
        tt = env_t(1.6); fr = 46 + 30 * np.exp(-tt / .05)
        return np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-tt / .35) + .5 * np.pad(noise(.3, 30, 900) * np.exp(-env_t(.3) / .05), (0, int(1.3 * SR)))
    if k == "twang":
        tt = env_t(1.2); fr = 150 + 40 * np.exp(-tt / .1)
        ph = 2 * np.pi * np.cumsum(fr) / SR
        return (np.sin(ph) + .5 * np.sin(2 * ph) + .3 * np.sin(3.01 * ph)) * np.exp(-tt / .25) * .7
    if k in ("roll", "whoosh", "rope", "creak", "spiral"):
        d = e["dur"]; tt = env_t(d); n = len(tt)
        if k == "roll":
            lo, hi = 80, 900 + 2500 * e["bright"]; x = noise(d, lo, hi)
            ramp = np.linspace(.3, 1, n) if e["rise"] > 0 else np.linspace(1, .2, n)
            return x * ramp * (1 + .3 * np.sin(2 * np.pi * 9 * tt)) * .5
        if k == "whoosh": return noise(d, 300, 2500) * np.sin(np.pi * tt / d) ** 2 * .6
        if k == "rope":   return noise(d, 1500, 7000) * np.linspace(1, .3, n) * .5
        if k == "creak":
            fr = 90 + 20 * np.sin(2 * np.pi * .7 * tt); p = 2 * np.pi * np.cumsum(fr) / SR
            return (np.sign(np.sin(p)) * .3) * bandlimit(np.abs(rng.standard_normal(n)), 200, 2000) * np.sin(np.pi * tt / d) * .4
        if k == "spiral":   # 螺旋漏斗：半径变小 -> 绕行频率升高 -> 滚动声的周期调制和音高同时上升
            orb = 2 + 22 * (tt / d) ** 2; ph = 2 * np.pi * np.cumsum(orb) / SR
            tone = np.sin(2 * np.pi * np.cumsum(300 + 900 * (tt / d) ** 2) / SR) * .15
            return (noise(d, 150, 3000) * (1 + .6 * np.sin(ph)) * .4 + tone) * np.minimum(1, tt / .1) * (0.6 + 0.6 * tt / d)
    raise ValueError(k)

N = int((END + 0.5) * SR); mix = np.zeros((N, 2))
for e in events():
    y = synth(e) * e["gain"]; i = int(e["t"] * SR); j = min(N, i + len(y))
    p = (e["pan"] + 1) * np.pi / 4
    mix[i:j, 0] += y[: j - i] * np.cos(p); mix[i:j, 1] += y[: j - i] * np.sin(p)

# 房间混响：合成脉冲响应（工作间，RT60 约 0.7s，高频衰减更快）
L = int(1.2 * SR); tt = np.arange(L) / SR
for ch in range(2):
    ir = rng.standard_normal(L) * np.exp(-6.9 * tt / 0.7)
    ir = bandlimit(ir, 100, 7000); ir[0] = 0
    wet = np.fft.irfft(np.fft.rfft(mix[:, ch], N + L) * np.fft.rfft(ir, N + L), N + L)[:N]
    mix[:, ch] = mix[:, ch] + 0.08 * wet / np.max(np.abs(ir))
mix += 0.0015 * np.stack([noise(N / SR, 40, 400)[:N] for _ in range(2)], 1)   # 极低的房间底噪
fade = int(2.0 * SR); mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
mix *= 10 ** (-1 / 20) / np.max(np.abs(mix))
path = os.path.join(OUT, "节奏小样_v0.wav")
with wave.open(path, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype("<i2").tobytes())
print("wrote", path, f"{N / SR:.1f}s")
