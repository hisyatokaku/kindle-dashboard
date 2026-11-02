#!/bin/sh
# 毎時 MINUTE 分にダッシュボード画像を取得して全画面表示し、次の更新まで休止する。
# 終了するには電源ボタン長押しで再起動する。
URL="https://hisyatokaku.github.io/kindle-dashboard/dashboard.png"
MINUTE=20 # GitHub Actions (毎時5分開始) の完了を待ってから取得する
DIR=/mnt/us/dashboard
PNG=/tmp/dashboard.png
LOG=$DIR/dashboard.log

log() { echo "$(date '+%F %T') $*" >>"$LOG"; }

log "start"
# Kindle の通常画面を止める (5.x 世代)
stop framework >/dev/null 2>&1
stop lab126_gui >/dev/null 2>&1
lipc-set-prop com.lab126.powerd preventScreenSaver 1

while true; do
  # Wi-Fi が使えるようになるまで最大 60 秒待つ
  i=0
  until ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1 || [ $i -ge 30 ]; do
    sleep 2
    i=$((i + 1))
  done

  if curl -fsSL --max-time 60 -o "$PNG.tmp" "$URL"; then
    mv "$PNG.tmp" "$PNG"
    eips -f -g "$PNG"
    log "updated (battery $(gasgauge-info -c))"
  else
    log "fetch failed"
  fi

  sleep 10 # 休止に入る前の猶予

  # 次の毎時 MINUTE 分までの秒数 (JST は UTC+9 で時の境界が一致する)
  now=$(date +%s)
  next=$((now / 3600 * 3600 + MINUTE * 60))
  [ $next -le $((now + 60)) ] && next=$((next + 3600))

  # RTC で起床時刻を設定してサスペンド。失敗・早期起床時は残り時間を sleep で待つ
  if rtcwake -d /dev/rtc1 -m no -s $((next - now)) >/dev/null 2>&1; then
    echo mem >/sys/power/state
  else
    log "rtcwake failed, staying awake"
  fi
  remain=$((next - $(date +%s)))
  [ $remain -gt 0 ] && sleep $remain
done
