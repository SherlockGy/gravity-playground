#!/bin/zsh
# 重力乐园 · 从零重建：物理 -> 骨牌仿真 -> 物理（读入仿真）-> 建场景 -> 提取事件 -> 合成音频
set -e
cd "$(dirname "$0")/.."
BL=/Applications/Blender.app/Contents/MacOS/Blender
PY=/Applications/Blender.app/Contents/Resources/5.2/python/bin/python3.13
mkdir -p build/logs
$PY scripts/physics.py
$BL -b --factory-startup -P scripts/sim_dominoes.py > build/logs/sim_dominoes.log 2>&1
grep SIM_RESULT build/logs/sim_dominoes.log
$PY scripts/physics.py
$BL -b --factory-startup -P scripts/build_scene.py 2>&1 | grep -E "BUILD_OK|Error|Traceback|WARN"
$BL -b blend/重力乐园.blend -P scripts/extract_events.py 2>&1 | grep -E "EXTRACT_OK|Error|Traceback"
$PY scripts/synth_audio.py
