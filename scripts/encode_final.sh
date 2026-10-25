#!/bin/zsh
# 把序列帧 + 混音编码为成片。用法: scripts/encode_final.sh [--in renders/final] [--prores]
#   输出 renders/重力乐园_final_1080p.mp4（H.264 CRF 16 + AAC 320k）；--prores 另出 ProRes 422 HQ 母带 .mov
cd "$(dirname "$0")/.."
FF=${FFMPEG:-/Users/jgy/my_bins/ffmpeg}; IN=renders/final; PR=0; MIX=audio/mix/重力乐园_mix.wav
while [ $# -gt 0 ]; do case $1 in --in) IN=${2%/}; shift 2;; --prores) PR=1; shift;; *) echo "未知参数 $1"; exit 2;; esac; done
N=$(find $IN -name 'frame_*.png' -size +0 | wc -l | tr -d ' ')
[ "$N" -lt 1044 ] && echo "警告：只有 $N / 1044 帧，成片会在第一个缺帧处结束"
NAME=$(basename $IN); OUTV=renders/重力乐园_${NAME}_1080p.mp4; [ "$IN" = renders/final ] && OUTV=renders/重力乐园_final_1080p.mp4
$FF -loglevel error -stats -y -framerate 24 -start_number 1 -i $IN/frame_%04d.png -i $MIX -map 0:v -map 1:a \
  -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -profile:v high -movflags +faststart \
  -c:a aac -b:a 320k -shortest $OUTV
if [ $PR = 1 ]; then
  $FF -loglevel error -stats -y -framerate 24 -start_number 1 -i $IN/frame_%04d.png -i $MIX -map 0:v -map 1:a \
    -c:v prores_ks -profile:v 3 -pix_fmt yuv422p10le -c:a pcm_s24le ${OUTV%.mp4}_prores.mov
fi
ls -lh $OUTV ${OUTV%.mp4}_prores.mov 2>/dev/null
