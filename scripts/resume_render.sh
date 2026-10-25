#!/bin/zsh
# 兼容旧命令：等同于 scripts/render.sh start（推荐档，可续渲）。参数原样传给 render.sh
exec "$(dirname "$0")/render.sh" start "$@"
