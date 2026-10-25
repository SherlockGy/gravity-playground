# 进度检查点（Asia/Shanghai, 2026-10-24）
- [x] 物理/骨牌仿真/建场景/事件提取/音频合成：scripts/run_pipeline.sh 一键重建
- [x] sync_report：398 条设计接触中 384 条从烘焙动画提取并匹配；|误差| 95% 1.76 ms，最大 4.26 ms
- [x] 混音：-14.1 LUFS / -1.4 dBTP / LRA 12.6
- [x] EEVEE 预览：renders/preview/重力乐园_preview.mp4（12.7 MB），关键帧拼图 renders/preview/预览关键帧_contact_sheet.jpg
- [x] Cycles 满质量静帧 5 张：renders/preview/stills/，拼图 renders/preview/Cycles静帧_contact_sheet.jpg，42–56 s/帧
- [x] resume_render.sh / encode_final.sh；正式渲染 17:16 启动（日志 renders/final/render.log），约 48 s/帧，估计约 14 h
- [x] 设计文档第 11 节 + README 已更新
- [ ] 正式序列渲完后：scripts/encode_final.sh [--prores]

# v2（J 反馈 17:27）
- [x] 旧正式帧 14 张移到 renders/final/_obsolete_v1/
- [ ] 1 音频沙沙声诊断与修复
- [ ] 2 去砖墙、背景、材质
- [x] 3 镜头重设计（11 镜，build/camera.json），待检查帧
- [ ] 4 球入碗/急停审计
- [ ] 预览 + 静帧 + 拼图
- [x] 1 音频：原因=噪声型混响 IR（每个清脆撞击后拖宽带嘶声）+ 宽带噪声滚动层（沙沙）；已改模态混响 + 低频窄带滚动（待重建验证）
- [x] 4 天平：碟形托盘滚动摆 + 托盘下沉回弹 + 横梁冲量/油阻尼；急停审计 audit_stops.py，修了铜杯、配重绳、扳机板、木杯、风扇
- [x] 2 背景布/世界镜头射线近黑/木纹与磨损（待渲染检查）
- [x] 音频验证：audit_hiss.py 12 种撞击音色尾部 4–16k 平均约 -20 dB；混音 -14.0 LUFS / -1.4 dBTP / 385 事件
- [x] 检查帧（Cycles 25%）：修了木材洗白（Pointiness 去掉）、背景偏灰（幕布反照率 0.06→0.022）、灯光再降、22.8 s 构图、扳机杯近景、漏斗俯角 84→55° 与漏斗材质
- [x] 设计文档第 6 节重写 + 第 11b 节 + 说人话（v1 备份 build/设计方案_v1_backup.md）
- [x] 预览 v2：1044 帧 Cycles 24spp 960x540，约 2.7 s/帧，18:29 完成；renders/preview/重力乐园_preview_v2.mp4（7.5 MB）；拼图 renders/preview/预览关键帧_v2_contact_sheet.jpg
- [-] 满质量 Cycles 静帧 v2：按 J 要求（"先不急着Cycles渲染"）跳过；正式渲染未启动
- [ ] 待下次重建生效：分镜 F 天平微距俯角 10°→30°（脚本已改，预览里仍是 10°，碟里的珠子大半被碟沿挡住）；改后需 run_pipeline.sh 并重渲预览 480–571 帧
- [ ] 小差异：音频声像按 17:37 的机位计算，之后 H/J 两镜机位微调过（只影响左右声像，幅度很小），下次 run_pipeline.sh 自动对齐

# v3（J 反馈 18:35 起）
- [x] 镜头 A：原因=100 mm、0.42 m 机位只框住节拍器半个摆杆和半个棘轮，且 0.6–2.2 s 镜头在两者之间平移；改 70 mm 固定中近景，整套机构同框
- [x] 镜头 F：天平微距俯角 10°→30°，看得见碟里滚动的珠子
- [x] 画质档实测：EEVEE 8.7 / C32 14.4 / C64 23.3 / C128 40.0 s/帧（c64fast 25.3，无收益）；对比图 renders/bench/tiers_v2.jpg；推荐 64 spp ≈ 6.8 h
- [x] 最后的木杯：嵌进台面 3.2 cm，杯沿低于跑道面 1.2 cm；钢球 0.38 m/s 滚出跑道末端平抛入杯（最小间隙约 4 mm），落杯时刻不变；K 镜跟随段俯角升到 24°
- [x] 分珠器：真星轮（6 个齿槽）+ 护板 + 料管预存 5 颗珠；星轮 24.0 s 开始转，珠子从齿槽转到 0° 时落下（24.11 s 起每拍一颗），过水瓶的音符时刻不变；G 拆成 G1 配重 / G2 星轮近景（70 mm，快门 0.08）/ G3 水瓶横移
- [x] 重建：BUILD_OK 431 物体，385 事件，95% 1.78 ms，最大 4.26 ms；-14.0 LUFS
- [x] 预览 v3：重渲帧 1–58、480–745、880–1044（低采样），renders/preview/重力乐园_preview_v3.mp4（7.5 MB），拼图 预览关键帧_v3_contact_sheet.jpg
- [x] scripts/render.sh（start/status/stop/log，采样/引擎/分辨率/帧段/输出/运动模糊）+ render_setup.py + encode_final.sh --in/--prores；docs/渲染操作指南.md
- [x] 指南命令实测 14 项全部通过（单帧前台、后台启动、重复启动拒绝、跨目录拒绝、设置不一致拒绝、status、log、stop、续渲清理占位帧、小文件检查、EEVEE、mblur off、encode --in --prores、resume_render.sh）；修了 help 多打印一行；测试输出已删除；正式渲染未启动

# v4（J 反馈 19:38：钢球边缘）
- [x] 原因：镜面钢球映出深色幕布/木头，轮廓与背景融合；修复：steel_ball 材质（粗糙度 0.09–0.13）+ 钢球专用轮廓光条（light linking，只照 ball1 与牛顿摆球）
- [x] 对比图 renders/bench/steel_ball_edge.jpg（64 spp 1080p，帧 25/109/289）；64 spp 仍约 24 s/帧
- [ ] 预览 v4：重渲 1–330、960–1044 → renders/preview/重力乐园_preview_v4.mp4
- [-] 预览 v4：按 J 要求不再渲染（19:47 起改为"只构建、J 自己渲染"），已停止；frames_v2 现为 v3/v4 混合且不完整，最新完整预览仍是 renders/preview/重力乐园_preview_v3.mp4
- [x] 钢球轮廓修复已写入脚本（build_scene.py 的 steel_ball 材质；build_camera_lights.py 的 rim_* 光条 + light linking），run_pipeline.sh 重建后 .blend 中已验证（ball1 材质 steel_ball，14 条轮廓光）

# v5（J 反馈 19:49：开场脱扣）
- [x] 棘轮拨销 + 脱扣杠杆 + 挡板尾杆；钢珠静止贴住挡板；2.00 s 拨销顶杠杆（新增"咔"事件 trip_lever|ratchet|hit），2.01 s 挡板翻开，2.03 s 钢珠起滚
- [x] 镜头 A：70 mm 慢推 + 三段拉焦（节拍器 → 拨销 → 挡板/钢珠）
- [x] run_pipeline.sh：BUILD_OK 451 物体，385 事件，95% 0.63 ms，最大 4.03 ms，-14.1 LUFS；片长 43.5 s / 1044 帧不变（render.sh 与指南无需改）
- [x] 检查帧 1.95 s / 2.06 s（Cycles 50%）：拨销贴住杠杆 → 杠杆被顶起、挡板翻开、钢珠仍在原位
