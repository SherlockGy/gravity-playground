# 下载 Poly Haven 的 CC0 贴图与 HDRI（2K），记录到 THIRD_PARTY_NOTICES.md
# 运行: python3 scripts/fetch_assets.py
import json, os, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = {  # 资产 id -> 用途
    "american_walnut_veneer": "工作台面、胡桃木骨牌与大木块",
    "ash_veneer": "枫木滚轨、浅色木件",
    "cherry_veneer": "红木音条",
    "dark_brick_wall": "背景砖墙",
    "brown_planks_05": "搁板与机架",
}
HDRI = {"artist_workshop": "环境反射（低强度）"}
UA = {"User-Agent": "gravity-playground-asset-fetch/1.0"}
def get(u): return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA)))
def dl(u, p):
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(urllib.request.urlopen(urllib.request.Request(u, headers=UA)).read())
    return p
notes = []
for a, use in TEX.items():
    f = get(f"https://api.polyhaven.com/files/{a}")
    for m, key in [("diff", "Diffuse"), ("rough", "Rough"), ("nor", "nor_gl")]:
        dl(f[key]["2k"]["jpg"]["url"], f"{ROOT}/assets/tex/{a}/{m}.jpg")
    info = get(f"https://api.polyhaven.com/info/{a}")
    notes.append((a, info["name"], ", ".join(info["authors"]), use, f"https://polyhaven.com/a/{a}"))
for a, use in HDRI.items():
    f = get(f"https://api.polyhaven.com/files/{a}")
    dl(f["hdri"]["2k"]["hdr"]["url"], f"{ROOT}/assets/hdri/{a}_2k.hdr")
    info = get(f"https://api.polyhaven.com/info/{a}")
    notes.append((a, info["name"], ", ".join(info["authors"]), use, f"https://polyhaven.com/a/{a}"))
with open(f"{ROOT}/THIRD_PARTY_NOTICES.md", "w") as fp:
    fp.write("# 第三方素材与授权\n\n本片所有声音均为程序合成，未使用任何采样。以下视觉素材全部来自 Poly Haven，授权为 CC0（公共领域，可商用、无需署名；此处仍按惯例注明作者）。\n\n")
    fp.write("| 资产 | 名称 | 作者 | 用途 | 链接 |\n|---|---|---|---|---|\n")
    for n in notes: fp.write("| " + " | ".join(n) + " |\n")
    fp.write("\n授权说明：https://polyhaven.com/license\n")
print("\n".join(str(n) for n in notes))
