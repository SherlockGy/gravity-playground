# 重力乐园 · 物理建模音频合成（只用 numpy；响度/真峰值用 ffmpeg 测量与限制）
# 输入：audio/events/events.json（extract_events.py 从烘焙动画里提取的真实接触事件）
# 输出：audio/mix/重力乐园_mix.wav（48 kHz / 24-bit / 立体声，-14 LUFS，真峰值 ≤ -1 dBTP）
#       audio/mix/mix_report.json（响度测量、事件数）
# 用法: <Blender自带python> scripts/synth_audio.py
# 每个声音都由画面中的物体决定：材质 -> 模态频率比与衰减；音高 -> 物体尺寸（timeline 中的音符）；
# 力度 -> 提取到的速度突变 |Δv|；声像 -> 接触点在镜头画面中的横向位置；距离 -> 轻微衰减与混响比。
import os, sys, json, math, subprocess, re
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import timeline as TL
SR = 48000; FFMPEG = "/Users/jgy/my_bins/ffmpeg"
ev = json.load(open(os.path.join(ROOT, "audio", "events", "events.json")))
E = ev["events"]; ROLLS = ev["rolls"]; END = ev["end"]
N = int(round((END + 0.0) * SR))
TAIL = int(4.0 * SR)
L = np.zeros(N + TAIL); R = np.zeros(N + TAIL)
rng = np.random.default_rng(20261024)

def nf(name): return TL.NOTE[name]
class Sig(np.ndarray):
    """长度不同的声音片段相加时自动补零对齐（起点对齐）"""
    def __add__(s, o):
        if isinstance(o, np.ndarray) and o.ndim == 1 and len(o) != len(s):
            n = max(len(s), len(o)); a = np.zeros(n); a[:len(s)] += np.asarray(s); a[:len(o)] += np.asarray(o); return a.view(Sig)
        return np.ndarray.__add__(s, o)
    __radd__ = __add__
def env_exp(n, tau): return np.exp(-np.arange(n) / (tau * SR))
def modal(freqs, amps, taus, dur, attack=0.0006, phase_rand=True):
    n = int(dur * SR); t = np.arange(n) / SR; y = np.zeros(n)
    for f, a, tau in zip(freqs, amps, taus):
        if f >= SR * 0.45: continue
        ph = rng.uniform(0, 2 * np.pi) if phase_rand else 0
        y += a * np.sin(2 * np.pi * f * t + ph) * np.exp(-t / tau)
    na = max(1, int(attack * SR)); y[:na] *= np.linspace(0, 1, na)
    return y.view(Sig)
def noise_burst(dur, lo, hi, tau):
    n = int(dur * SR); x = rng.standard_normal(n)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    X *= ((f > lo) & (f < hi)).astype(float); y = np.fft.irfft(X, n)
    y /= (np.abs(y).max() + 1e-9); return (y * env_exp(n, tau)).view(Sig)
def bandnoise(n, peaks):
    """peaks: [(f, bw, gain)] -> 频域塑形的噪声"""
    x = rng.standard_normal(n); X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR); H = np.zeros_like(f)
    for (fc, bw, g) in peaks: H += g * np.exp(-0.5 * ((f - fc) / bw) ** 2)
    y = np.fft.irfft(X * H, n); return y / (np.std(y) + 1e-9)

# ---------- 乐器（材质） ----------
BEAM = [1.0, 2.756, 5.404, 8.933]              # 两端自由梁/悬挂管
MARIMBA = [1.0, 3.93, 9.24]                     # 调音后的木质音条
BOWL = [1.0, 2.32, 4.25, 6.63]                  # 碗/杯
BELL = [0.5, 1.0, 1.183, 1.506, 2.0, 2.514, 2.662, 3.011, 4.166]   # 教堂钟分音（hum, prime, tierce, quint, nominal...）
def v_marimba(f, s):   # 钢珠落在红木音条上：硬槌，明亮
    y = modal([f * r for r in MARIMBA], [1, 0.32 * s, 0.10 * s], [0.55 * (600 / f) ** 0.5, 0.09, 0.03], 1.6)
    return y + 0.25 * s * noise_burst(0.02, 2000, 9000, 0.002)
def v_glass_tube(f, s):
    y = modal([f * r for r in BEAM], [1, 0.45, 0.22, 0.10], [2.2, 1.1, 0.5, 0.25], 3.5)
    return y + 0.15 * noise_burst(0.01, 4000, 14000, 0.0015)
def v_bowl(f, s):
    y = modal([f * r for r in BOWL], [1, 0.38, 0.16, 0.07], [0.9, 0.42, 0.2, 0.1], 2.2)
    return y + 0.2 * noise_burst(0.015, 2500, 10000, 0.002)
def v_bottle(f, s):   # 盛水玻璃瓶：基音 + 稀疏泛音，略带水的阻尼
    y = modal([f, f * 2.08, f * 3.62, f * 5.3], [1, 0.30, 0.12, 0.05], [1.3, 0.5, 0.25, 0.12], 2.6)
    return y + 0.12 * noise_burst(0.01, 3000, 12000, 0.0015)
def v_chime(f, s):
    return modal([f * r for r in BEAM], [1, 0.6, 0.3, 0.15], [3.2, 1.8, 0.9, 0.45], 4.0) + 0.2 * noise_burst(0.01, 5000, 16000, 0.001)
def v_cup(f, s, dur=2.5):
    return modal([f * r for r in BOWL], [1, 0.5, 0.25, 0.12], [1.4, 0.7, 0.35, 0.15], dur) + 0.2 * noise_burst(0.015, 2000, 9000, 0.002)
def v_bell(f):
    amps = [0.55, 0.8, 0.5, 0.25, 1.0, 0.3, 0.25, 0.2, 0.12]; taus = [9, 6, 5, 3.5, 4, 2.5, 2.2, 1.8, 1.2]
    y = modal([f * r for r in BELL], amps, taus, 9.0, attack=0.001)
    # 轻微拍频（钟体不完全对称）
    t = np.arange(len(y)) / SR; y *= 1 + 0.08 * np.sin(2 * np.pi * 1.3 * t)
    return y + 0.3 * noise_burst(0.03, 1500, 9000, 0.004)
def v_wood_click(f0, decay, bright=1.0):
    return modal([f0, f0 * 2.6, f0 * 4.2], [1, 0.5 * bright, 0.25 * bright], [decay, decay * 0.5, decay * 0.3], decay * 8) + 0.5 * noise_burst(0.01, f0, min(18000, f0 * 6), 0.0012)
def v_steel_click(f0=4700):   # 钢珠对钢珠：极短、极亮
    return modal([f0, f0 * 1.65, f0 * 2.4, 1900], [1, 0.6, 0.3, 0.35], [0.010, 0.007, 0.005, 0.02], 0.15, attack=0.0002) + 0.6 * noise_burst(0.004, 3000, 16000, 0.0006)
def v_thud(f0=110, dur=0.15, nb=0.6):   # 毛毡/重物：低频闷响
    t = np.arange(int(dur * SR)) / SR
    y = (np.sin(2 * np.pi * f0 * t * (1 - 0.15 * t / dur)) * np.exp(-t / (dur / 4))).view(Sig)
    return y + nb * noise_burst(dur, 60, 900, dur / 6)
def v_brass_click(f0=2400, decay=0.03):
    return modal([f0, f0 * 1.72, f0 * 2.9], [1, 0.6, 0.3], [decay, decay * 0.6, decay * 0.4], decay * 6, attack=0.0003) + 0.5 * noise_burst(0.005, 2000, 14000, 0.0008)
def v_rope_taut():   # 绳子突然绷紧 + 滑轮木架受力：低频冲击 + 短促“嘣”
    t = np.arange(int(0.9 * SR)) / SR
    boom = np.sin(2 * np.pi * (62 + 20 * np.exp(-t / 0.05)) * t) * np.exp(-t / 0.22)
    twang = modal([196, 392, 588, 790], [0.5, 0.3, 0.18, 0.1], [0.12, 0.08, 0.05, 0.03], 0.9)
    return boom.view(Sig) + 0.6 * twang + 0.5 * v_wood_click(420, 0.03)
def v_dom(k, mat):
    size = 0.04 + 0.08 * k / 55
    base = {"dom_porcelain": 3600, "dom_maple": 1900, "dom_walnut": 1300}[mat]
    f0 = base * (0.04 / size) ** 0.55 * rng.uniform(0.97, 1.03)
    dec = {"dom_porcelain": 0.012, "dom_maple": 0.018, "dom_walnut": 0.022}[mat] * (size / 0.04) ** 0.4
    y = v_wood_click(f0, dec, 1.2 if mat == "dom_porcelain" else 0.8)
    if mat == "dom_porcelain": y = y + 0.4 * modal([f0 * 2.1, f0 * 3.3], [1, 0.5], [0.05, 0.03], 0.3)
    return y * (size / 0.08) ** 0.6

def strength(e, ref):
    return float(np.clip((max(e["dv"], 1e-6) / ref) ** 0.6, 0.35, 1.4))
cats = {}
for e in E: cats.setdefault((e["mat_a"], e["mat_b"], e["kind"]), []).append(e["dv"])
REF = {k: float(np.median(v)) for k, v in cats.items()}

def place(y, t, pan, gain, depth):
    i0 = int(round(t * SR))
    if i0 >= len(L): return
    p = float(np.clip(pan, -1, 1)) * 0.85
    a = (p + 1) * np.pi / 4; dist = 1.0 / (1.0 + 0.18 * max(0.0, depth - 1.0))
    n = min(len(y), len(L) - i0)
    L[i0:i0 + n] += y[:n] * gain * dist * math.cos(a); R[i0:i0 + n] += y[:n] * gain * dist * math.sin(a)

used = {}
for e in E:
    key = (e["mat_a"], e["mat_b"], e["kind"]); s = strength(e, REF[key]); note = e.get("note")
    ma, mb, kd = key; y = None; g = 0.0
    if ma == "metro_arm": y, g = v_wood_click(2300, 0.012, 0.7), 0.10
    elif ma == "flap": y, g = v_brass_click(1800, 0.04), 0.22
    elif mb == "rosewood": y, g = v_marimba(nf(note), s), (0.55 if kd == "hit" else 0.16)
    elif mb == "brass_cup": y, g = v_cup(nf(note), s), (0.45 if kd == "hit" else 0.08)
    elif ma in ("lever", "pendulum", "hammer", "weight") and mb == "felt": y, g = v_thud(95 if ma != "weight" else 70, 0.18), 0.30 * s
    elif ma.startswith("dom_"): y, g = v_dom(int(e["a"][3:]), ma), 0.30
    elif ma == "cradle_plate": y, g = v_wood_click(700, 0.05) + v_brass_click(1500, 0.05), 0.35
    elif ma in ("cradle0", "cradle4") and mb.startswith("cradle"): y, g = v_steel_click(), 0.20 * s
    elif mb == "marble" and ma == "cradle4": y, g = v_steel_click(5600), 0.18
    elif mb == "glass_tube": y, g = v_glass_tube(nf(note), s), 0.32
    elif mb == "glass_rail": y, g = v_brass_click(6500, 0.006), 0.03
    elif mb == "ceramic": y, g = v_bowl(nf(note), s), 0.30
    elif mb == "pan": y, g = v_cup(nf(TL.PAN[1]) if kd == "hit" else nf(TL.PAN[1]), s, 3.0), (0.32 if kd == "hit" else 0.06)
    elif ma == "weight" and mb == "rope": y, g = v_rope_taut(), 0.65
    elif mb == "track": y, g = v_brass_click(2600, 0.05), 0.14
    elif mb == "bottle": y, g = v_bottle(nf(note), s), 0.20
    elif mb == "brass_track": y, g = v_brass_click(5200, 0.006), 0.025
    elif mb == "chime": y, g = v_chime(nf(note), s), 0.20 * s
    elif mb == "tcup": y, g = v_cup(1480, s, 1.2), 0.12
    elif ma == "tcup": y, g = v_brass_click(2100, 0.02) + 0.5 * v_thud(160, 0.06, 0.3), 0.30
    elif ma == "arm": y, g = v_thud(130, 0.22) + 0.4 * v_wood_click(600, 0.03), 0.6 * s
    elif mb == "copper": y, g = v_cup(523.25 * 0.8, s, 1.6), 0.30
    elif mb == "trigger2": y, g = v_brass_click(2000, 0.04), 0.30
    elif mb == "bell": y, g = v_bell(nf(TL.BELL[1])), 0.75
    elif mb == "wood_cup": y, g = v_wood_click(nf(note), 0.09, 0.6) + 0.3 * v_thud(nf(note), 0.2, 0.2), 0.45
    if y is None:
        print("WARN 无音色", key); continue
    used[key] = used.get(key, 0) + 1
    place(y, e["t"], e["pan"], g, e["depth"])

EV_L, EV_R = L.copy(), R.copy()     # 只含撞击事件的干声（用于分轨检查）
# ---------- 滚动声 ----------
# v2：滚动声改为“低频隆隆 + 轨道窄带共振”，去掉宽带高频噪声（v1 的宽带噪声听起来像沙沙声）
SURF = {"maple": [(170, 45, 1), (420, 22, 0.6), (980, 28, 0.22)], "walnut": [(140, 40, 1), (360, 22, 0.5), (820, 26, 0.18)],
        "glass": [(240, 50, 0.6), (900, 14, 0.5), (2300, 20, 0.25)], "brass": [(220, 45, 0.7), (1250, 12, 0.5), (2600, 18, 0.22)],
        "copper": [(150, 40, 0.5), (420, 7, 1.2), (1130, 10, 1.0), (2050, 15, 0.6)], "air": [(160, 60, 1), (520, 120, 0.4)]}
def lowpass(y, fc):
    n = len(y); Y = np.fft.rfft(y); f = np.fft.rfftfreq(n, 1 / SR); Y /= (1 + (f / fc) ** 4); return np.fft.irfft(Y, n)
R_BALL = {"ball1": 0.0125, "marble0": 0.008, "ball2": 0.015}
for r in ROLLS:
    t = np.array(r["t"]); sp = np.array(r["speed"]); i0 = int(round(r["t0"] * SR)); i1 = int(round(r["t1"] * SR))
    n = i1 - i0
    if n <= 16: continue
    ts = r["t0"] + np.arange(n) / SR; v = np.interp(ts, t, sp)
    surf = r["mat"] if r["mat"] in SURF else ("brass" if ("brass" in r["mat"] or "pan" in r["mat"]) else "walnut")
    if r["obj"] == "fan":     # 调速风扇：两叶，叶片通过频率 = 2 × 转速
        f_bp = 2 * v / (2 * np.pi); ph = 2 * np.pi * np.cumsum(f_bp) / SR
        y = bandnoise(n, SURF["air"]) * (0.55 + 0.45 * np.sin(ph) ** 2) * np.clip(v / 29.3, 0, 1) * 0.020
        y += 0.010 * np.sin(np.cumsum(2 * np.pi * (f_bp * 6)) / SR) * np.clip(v / 29.3, 0, 1)
    else:
        y = lowpass(bandnoise(n, SURF[surf]), 2500) * (np.clip(v, 0, None) / 0.5) ** 1.5
        rb = R_BALL.get(r["obj"], 0.008)     # 球每转一圈的轻微起伏（球面不完美）
        y *= 0.8 + 0.2 * np.sin(np.cumsum(2 * np.pi * v / (2 * np.pi * rb)) / SR)
        gain = {"maple": 0.022, "walnut": 0.018, "glass": 0.008, "brass": 0.007, "copper": 0.035}[surf]
        if surf == "copper" and r["t1"] - r["t0"] > 1:      # 漏斗：绕圈频率 f = v^3 / (2π g k)，越转越快
            f_orb = v ** 3 / (2 * np.pi * 9.81 * 0.0075); ph = 2 * np.pi * np.cumsum(f_orb) / SR
            y *= 0.6 + 0.4 * np.sin(ph)
        y *= gain
    fade = min(n // 4, int(0.01 * SR)); y[:fade] *= np.linspace(0, 1, fade); y[-fade:] *= np.linspace(1, 0, fade)
    # 声像：取该段中点附近事件的声像（同一物体）
    near = [e for e in E if (e["a"] == r["obj"] or e["b"] == r["obj"]) and r["t0"] - 0.6 <= e["t"] <= r["t1"] + 0.6]
    pan = float(np.mean([e["pan"] for e in near])) if near else 0.0
    place(y, r["t0"], pan, 1.0, 1.0)

# ---------- 房间混响（合成脉冲响应：木作坊，RT60≈1.0 s） ----------
def ir(seed):
    # v2：模态混响。v1 用“指数衰减白噪声”作脉冲响应，每个清脆的撞击后都会拖出一段宽带“嘶嘶/沙沙”尾巴，
    # 在开头只有节拍器的稀疏段尤其明显。这里改为 2500 个随机房间模态的叠加，高频衰减得比低频快（真实房间的空气与材料吸收），
    # 尾巴是平滑的“嗡”而不是噪声。
    g = np.random.default_rng(seed); n = int(1.4 * SR); t = np.arange(n) / SR; y = np.zeros(n)
    fm = np.exp(g.uniform(np.log(90), np.log(7000), 2500)); am = g.standard_normal(2500) / np.sqrt(fm / 300 + 1)
    T60 = 0.9 * (fm / 500) ** -0.35; T60 = np.clip(T60, 0.12, 1.3); ph = g.uniform(0, 2 * np.pi, 2500)
    for k in range(0, 2500, 100):
        sl = slice(k, k + 100)
        y += (am[sl, None] * np.sin(2 * np.pi * fm[sl, None] * t[None] + ph[sl, None]) * np.exp(-6.9 * t[None] / T60[sl, None])).sum(0)
    na = int(0.02 * SR); y[:na] *= np.linspace(0, 1, na)
    pre = int(0.014 * SR); y = np.concatenate([np.zeros(pre), y])
    for d, a in ((0.007, 0.5), (0.011, 0.35), (0.019, 0.3), (0.023, 0.22)):   # 早期反射（台面、墙）
        y[int(d * SR)] += a * np.abs(y).max()
    return y / np.sqrt(np.sum(y ** 2))
def conv(x, h):
    n = len(x) + len(h) - 1; nfft = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(h, nfft), nfft)[:len(x)]
hL, hR = ir(1), ir(2)
wet = 0.16
WL, WR = wet * conv(L, hL), wet * conv(R, hR)
Lm = L + WL; Rm = R + WR
if os.environ.get("STEMS"):     # 分轨：events / rolls / reverb（未做响度处理，统一缩放）
    import wave as _w
    sd = os.path.join(ROOT, "audio", "stems"); os.makedirs(sd, exist_ok=True)
    pk = max(np.abs(Lm).max(), np.abs(Rm).max()) / 0.5
    for nm, (a_, b_) in dict(events=(EV_L, EV_R), rolls=(L - EV_L, R - EV_R), reverb=(WL, WR)).items():
        x = np.stack([a_[:N], b_[:N]], 1) / pk
        with _w.open(os.path.join(sd, nm + ".wav"), "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(np.round(np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
# 只保留片长 + 0.0（画面结束即结束，最后 0.3 s 淡出混响尾巴）
Lm = Lm[:N]; Rm = Rm[:N]; fo = int(0.3 * SR)
Lm[-fo:] *= np.linspace(1, 0, fo) ** 2; Rm[-fo:] *= np.linspace(1, 0, fo) ** 2
mix = np.stack([Lm, Rm], 1); mix /= np.abs(mix).max() / 0.5

def write_wav(path, x, bits=24):
    import wave
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(bits // 8); w.setframerate(SR)
        if bits == 24:
            iv = np.round(x * 8388607).astype("<i4"); b = iv.tobytes(); b = np.frombuffer(b, np.uint8).reshape(-1, 4)[:, :3].tobytes()
        else:
            b = np.round(x * 32767).astype("<i2").tobytes()
        w.writeframes(b)
out = os.path.join(ROOT, "audio", "mix"); os.makedirs(out, exist_ok=True)
pre = os.path.join(out, "_pre.wav"); write_wav(pre, mix)
def measure(path):
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1]); TP = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)[-1])
    LRA = float(re.findall(r"LRA:\s+(-?[\d.]+) LU", r)[-1]); return I, TP, LRA
I0, TP0, _ = measure(pre)
target = -14.0
final = os.path.join(out, "重力乐园_mix.wav")
gain_db = target - I0
for it in range(4):
    # 增益 -> 4 倍过采样上做峰值限制（等效真峰值限制）-> 回到 48 kHz
    lim = 10 ** (-1.4 / 20)
    af = f"volume={gain_db:.3f}dB,aresample=192000,alimiter=limit={lim:.4f}:attack=1:release=60:level=disabled,aresample=48000"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", pre, "-af", af, "-c:a", "pcm_s24le", final], check=True)
    I, TP, LRA = measure(final)
    if abs(I - target) <= 0.3 and TP <= -1.0: break
    gain_db += (target - I)
os.remove(pre)
rep = dict(integrated_lufs=I, true_peak_dbtp=TP, lra_lu=LRA, pre_gain_db=gain_db, events=len(E), voices_used={"|".join(k): v for k, v in used.items()},
           rolls=len(ROLLS), sr=SR, duration_s=N / SR)
json.dump(rep, open(os.path.join(out, "mix_report.json"), "w"), indent=1, ensure_ascii=False)
print("MIX_OK", json.dumps({k: rep[k] for k in ("integrated_lufs", "true_peak_dbtp", "lra_lu", "events", "duration_s")}))
