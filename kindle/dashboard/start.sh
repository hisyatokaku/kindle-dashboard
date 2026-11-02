#!/bin/sh
# KUAL から呼ばれる。KUAL (framework) を止めても生き残るよう切り離して起動する
nohup /bin/sh /mnt/us/dashboard/dashboard.sh >/dev/null 2>&1 &
