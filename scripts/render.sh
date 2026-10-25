#!/bin/zsh
# 重力乐园 渲染控制。用法（在项目目录或任意位置都可以）：
#   scripts/render.sh start  [--samples 64] [--engine cycles|eevee] [--percent 100] [--frames 1-1044]
#                            [--out renders/final] [--mblur auto|off] [--fg] [--force]
#   scripts/render.sh status [--out DIR]      进度 / 剩余时间估计
#   scripts/render.sh stop   [--out DIR]      安全停止（已完成的帧保留，下次 start 自动续渲）
#   scripts/render.sh log    [--out DIR]      实时看日志（Ctrl+C 退出查看，不影响渲染）
# 默认 = 推荐档：Cycles 64 spp + 降噪，1920×1080，运动模糊按分镜表（auto），输出 renders/final/frame_0001.png…
setopt nullglob
cd "$(dirname "$0")/.."
BL=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
CMD=${1:-help}; shift 2>/dev/null
SAMPLES=64; ENGINE=cycles; PCT=100; FRAMES=1-1044; OUT=renders/final; MBLUR=auto; FG=0; FORCE=0
while [ $# -gt 0 ]; do
  case $1 in
    --samples) SAMPLES=$2; shift 2;;  --engine) ENGINE=$2; shift 2;;  --percent) PCT=$2; shift 2;;
    --frames) FRAMES=$2; shift 2;;    --out) OUT=${2%/}; shift 2;;     --mblur) MBLUR=$2; shift 2;;
    --fg) FG=1; shift;;               --force) FORCE=1; shift;;
    *) echo "未知参数: $1"; exit 2;;
  esac
done
S=${FRAMES%-*}; E=${FRAMES#*-}; [ "$S" = "$FRAMES" ] && E=$S
PIDF=$OUT/.render.pid; LOG=$OUT/render.log; CONF=$OUT/render_settings.txt
alive() { [ -f $PIDF ] && kill -0 $(head -1 $PIDF) 2>/dev/null; }
count() { local n=0; for f in $OUT/frame_*.png; do [ -s "$f" ] && n=$((n+1)); done; echo $n; }
case $CMD in
start)
  [ -x "$BL" ] || { echo "找不到 Blender：$BL（可用 BLENDER=/路径/Blender 指定）"; exit 1; }
  mkdir -p $OUT
  if alive; then echo "已经在渲染中（PID $(head -1 $PIDF)），拒绝重复启动。看进度：scripts/render.sh status --out $OUT"; exit 1; fi
  if pgrep -f "scripts/render_setup.py" >/dev/null && [ $FORCE = 0 ]; then
    echo "检测到另一个渲染进程（PID $(pgrep -f scripts/render_setup.py | tr '\n' ' ')）在跑，可能是别的输出目录。同时跑两个会互相拖慢。确实要并行请加 --force"; exit 1; fi
  NEWCONF="engine=$ENGINE samples=$SAMPLES percent=$PCT mblur=$MBLUR"
  if [ -f $CONF ] && [ "$(cat $CONF)" != "$NEWCONF" ] && [ $(count) -gt 0 ] && [ $FORCE = 0 ]; then
    echo "这个输出目录里已有用不同设置渲的帧：$(cat $CONF)"; echo "本次设置：$NEWCONF"
    echo "混在一起会画质不一致。请换 --out 目录，或删掉旧帧，或确认无所谓时加 --force"; exit 1; fi
  echo $NEWCONF > $CONF
  # 清理中断留下的 0 字节占位帧和不完整的 PNG（PNG 必须以 IEND 块结尾）
  for f in $OUT/frame_*.png; do
    if [ ! -s "$f" ] || [ "$(tail -c 8 "$f" | xxd -p)" != "49454e44ae426082" ]; then echo "删除不完整帧 $f"; rm -f "$f"; fi
  done
  echo "$(date '+%F %T') 开始/续渲 帧 $S-$E，$NEWCONF，已有 $(count) 帧" | tee -a $LOG
  export GL_ENGINE=$ENGINE GL_SAMPLES=$SAMPLES GL_PCT=$PCT GL_MBLUR=$MBLUR GL_START=$S GL_END=$E GL_OUT=$OUT
  if [ $FG = 1 ]; then
    echo $$ > $PIDF; caffeinate -i $BL -b blend/重力乐园.blend -P scripts/render_setup.py -a 2>&1 | tee -a $LOG | grep -E "RENDER_SETUP|Saved|Error"; rm -f $PIDF
  else
    nohup caffeinate -i $BL -b blend/重力乐园.blend -P scripts/render_setup.py -a >> $LOG 2>&1 &
    echo $! > $PIDF
    echo "已在后台启动（PID $!，关掉终端也会继续，Mac 不会自动睡眠）。进度：scripts/render.sh status --out $OUT"
  fi;;
status)
  N=$(count); TOT=$(( E - S + 1 ))
  if alive; then echo "状态：渲染中（PID $(head -1 $PIDF)）"; else echo "状态：没有在渲染"; fi
  [ -f $CONF ] && echo "设置：$(cat $CONF)"
  echo "已完成：$N 帧（全片 1044 帧；目录 $OUT）"
  T=$(grep -oE "Time: [0-9:.]+" $LOG 2>/dev/null | tail -10 | awk '{split($2,a,":"); s+=a[1]*60+a[2]; n++} END{if(n) printf "%.1f", s/n}')
  if [ -n "$T" ]; then
    REM=$(( 1044 - N )); [ $REM -lt 0 ] && REM=0
    echo "最近 10 帧平均 ${T} 秒/帧；按全片 1044 帧算还剩 $REM 帧，约 $(echo "$REM*$T/3600" | bc -l | xargs printf '%.1f') 小时【估计】"
  fi;;
stop)
  if alive; then P=$(head -1 $PIDF); pkill -TERM -P $P 2>/dev/null; kill -TERM $P 2>/dev/null; sleep 2
    echo "已停止（PID $P）。正在渲的那一帧会作废，下次 start 自动清理并续渲。"; rm -f $PIDF
  else echo "没有在渲染（$OUT）"; fi;;
log) tail -f $LOG;;
*) sed -n 2,8p $0;;
esac
