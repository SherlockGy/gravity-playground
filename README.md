# 重力乐园 · Gravity Playground

一支 43.5 秒、16:9（1920×1080，24 fps）的 Blender 写实短片：一台从左到右横向展开、全长约 15.6 m 的连锁机关，由木、铜、钢、玻璃、陶瓷、铸铁等材质组成。每一次碰撞都是一个音符，全片声音都来自画面中的物体，连成一段 120 BPM、D 大调五声音阶的乐句。

**[下载正式成片](https://github.com/SherlockGy/gravity-playground/releases/download/v1.0.0/gravity-playground-1080p.mp4)** · [成片与混音下载](https://github.com/SherlockGy/gravity-playground/releases/tag/v1.0.0)

仓库保留源码、Blender 工程、贴图、音频及构建数据；渲染序列、预览缓存、日志和 Blender 自动备份不纳入 Git。设计与执行中的变更见 [`docs/设计方案.md`](docs/设计方案.md) 第 11 节，历史进度检查点见 `build/progress.md`。

## 流水线（timeline.py 是唯一时间来源）

```
timeline.py ─► physics.py ─► sim_dominoes.py(Bullet) ─► physics.py ─► build_scene.py(+build_camera_lights.py) ─► blend/重力乐园.blend
                                                                                 │
                                      extract_events.py（从烘焙动画提取接触）◄──────┘
                                                 │
                                      synth_audio.py ─► audio/mix/重力乐园_mix.wav
```

## 目录与脚本

```
scripts/
├── timeline.py            全片时间轴、音符、拍点
├── physics.py             解析物理：反算几何、生成全部轨迹与设计碰撞日志 -> build/motion.json
├── sim_dominoes.py        骨牌 Bullet 仿真 + 二分调间距 -> build/domino_sim.{json,npz}
├── build_scene.py         建模、材质、写入动画 -> blend/重力乐园.blend
├── build_camera_lights.py 11 镜分镜摄影机（逐镜快门/焦点）与灯光（被 build_scene.py 调用），镜头日志 build/camera.json
├── blib.py                建模/材质/关键帧工具
├── extract_events.py      从 .blend 动画中提取碰撞 -> audio/events/events.json, build/sync_report.md
├── synth_audio.py         物理建模合成 + 混响 + 响度 -> audio/mix/
├── run_pipeline.sh        以上全部一键重建（约 1 分钟）
├── render_checks.py       指定时刻的检查帧
├── preview_setup.py       预览序列设置（v2：Cycles 24 spp + 降噪，960×540，输出 renders/preview/frames_v2）
├── render_stills.py       Cycles 满质量静帧 + 计时 -> renders/preview/stills/, build/cycles_timing.json
├── audit_hiss.py          逐音色检查尾部高频噪声（v1 噪声混响 vs v2 模态混响）
├── audit_stops.py         扫描所有运动物体的"急停"
├── final_setup.py / gpu.py 正式 Cycles 设置 / 启用 Metal
├── resume_render.sh       启动或续渲正式序列（后台，可反复执行）
├── encode_final.sh        序列帧 + 混音 -> MP4（可选 --prores 母带）
├── fetch_assets.py        下载 Poly Haven CC0 贴图与 HDRI
└── legacy/                设计阶段脚本（sketch_audio.py 已不适配新时间轴）
```

## 常用命令

```bash
./scripts/run_pipeline.sh        # 物理 -> 场景 -> 事件 -> 音频，全部重建
STEMS=1 python3 scripts/synth_audio.py   # 额外导出分轨 audio/stems/（调试用）
./scripts/resume_render.sh       # 正式渲染 / 中断后续渲（日志 renders/final/render.log）
./scripts/encode_final.sh        # 渲完后编码成片 renders/重力乐园_final_1080p.mp4
```

## 环境

- Blender 5.2.2 LTS（Apple M1 Pro，Metal GPU），ffmpeg：`/Users/jgy/my_bins/ffmpeg`
- 贴图/HDRI 来自 Poly Haven（CC0），见 `THIRD_PARTY_NOTICES.md`；声音全部程序合成，无采样。

## 版本

- v2（2026-10-24）：去尾音沙沙声（模态混响 + 窄带滚动声）、深色幕布背景、11 镜分镜重拍并逐镜控制运动模糊、天平与多处急停改为有动量的运动。详见 docs/设计方案.md 第 6 节与第 11b 节。v1 预览帧在 renders/preview/_v1/。
- v4–v5（2026-10-24 晚）：钢球轮廓光 + steel_ball 材质；开场改为棘轮拨销顶起脱扣杠杆、挡板翻开放珠（新增"咔"声）。详见设计方案第 11d、11e 节。渲染方法见 docs/渲染操作指南.md。
