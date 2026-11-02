"""Kindle 用ダッシュボード画像 (600x800 グレースケール PNG) を生成する。

天気: Open-Meteo / ニュース: NHK RSS
使い方: python generate.py [出力パス]  (既定: public/dashboard.png)
"""
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 600, 800
JST = timezone(timedelta(hours=9))
LAT, LON = 35.694, 139.7536  # 東京都千代田区
WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    "&current=temperature_2m,weather_code"
    "&hourly=temperature_2m,weather_code,precipitation_probability"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
    "&timezone=Asia%2FTokyo&forecast_days=3"
)
NEWS_URL = "https://www.nhk.or.jp/rss/news/cat0.xml"

FONT_CANDIDATES = {
    "regular": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    ],
    "bold": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    ],
}

WMO = {
    0: "快晴", 1: "晴れ", 2: "晴れ時々曇り", 3: "曇り",
    45: "霧", 48: "霧",
    51: "霧雨", 53: "霧雨", 55: "霧雨", 56: "着氷性霧雨", 57: "着氷性霧雨",
    61: "小雨", 63: "雨", 65: "大雨", 66: "着氷性の雨", 67: "着氷性の雨",
    71: "小雪", 73: "雪", 75: "大雪", 77: "霧雪",
    80: "にわか雨", 81: "にわか雨", 82: "激しいにわか雨",
    85: "にわか雪", 86: "激しいにわか雪",
    95: "雷雨", 96: "雷雨・ひょう", 99: "雷雨・ひょう",
}
# 時間別の狭い枠用の短い表記
WMO_SHORT = {2: "晴時々曇", 56: "霧雨", 57: "霧雨", 66: "雨", 67: "雨", 82: "強い雨", 86: "強い雪", 96: "雷雨", 99: "雷雨"}
WEEKDAYS = "月火水木金土日"


def font(weight, size):
    for path in FONT_CANDIDATES[weight]:
        if Path(path).exists():
            # Noto CJK の ttc は index 0 が JP
            return ImageFont.truetype(path, size, index=0)
    raise FileNotFoundError(f"日本語フォントが見つかりません: {weight}")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "kindle-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def wrap(draw, text, fnt, max_width):
    lines, line = [], ""
    for ch in text:
        if draw.textlength(line + ch, font=fnt) > max_width:
            lines.append(line)
            line = ch
        else:
            line += ch
    if line:
        lines.append(line)
    return lines


def draw_weather(draw, now, y):
    w = json.loads(fetch(WEATHER_URL))
    cur, daily, hourly = w["current"], w["daily"], w["hourly"]

    # 現在の天気（左）
    draw.text((30, y), f"{round(cur['temperature_2m'])}°", font=font("bold", 96), fill=0)
    draw.text((30, y + 125), WMO.get(cur["weather_code"], "-"), font=font("bold", 30), fill=0)
    draw.text((30, y + 170), "千代田区", font=font("regular", 20), fill=80)

    # この先 12 時間（右）: 3 時間おき 4 枠
    times = hourly["time"]
    start = next(i for i, t in enumerate(times) if t >= now.strftime("%Y-%m-%dT%H:00"))
    x0, colw = 260, 82
    f_small, f_mid = font("regular", 20), font("bold", 26)
    for k in range(4):
        i = start + 3 * (k + 1)
        if i >= len(times):
            break
        x = x0 + k * colw
        draw.text((x, y + 10), f"{int(times[i][11:13])}時", font=f_small, fill=0)
        draw.text((x, y + 45), f"{round(hourly['temperature_2m'][i])}°", font=f_mid, fill=0)
        draw.text((x, y + 85), WMO_SHORT.get(hourly["weather_code"][i]) or WMO.get(hourly["weather_code"][i], "-"), font=f_small, fill=0)
        draw.text((x, y + 120), f"☂{hourly['precipitation_probability'][i]}%", font=f_small, fill=0)

    # 3 日間の予報
    y += 215
    draw.line((30, y, W - 30, y), fill=160, width=1)
    labels = ["今日", "明日", "明後日"]
    colw = (W - 60) // 3
    for d in range(3):
        x = 30 + d * colw
        draw.text((x, y + 12), labels[d], font=font("bold", 22), fill=0)
        draw.text((x, y + 44), WMO.get(daily["weather_code"][d], "-"), font=font("regular", 22), fill=0)
        hi, lo = round(daily["temperature_2m_max"][d]), round(daily["temperature_2m_min"][d])
        draw.text((x, y + 76), f"{hi}° / {lo}°", font=font("regular", 22), fill=0)
        draw.text((x, y + 106), f"☂{daily['precipitation_probability_max'][d]}%", font=font("regular", 20), fill=0)
    return y + 145


def draw_news(draw, y):
    root = ET.fromstring(fetch(NEWS_URL))
    titles = [i.findtext("title", "").strip() for i in root.iter("item")]

    draw.rectangle((0, y, W, y + 44), fill=0)
    draw.text((30, y + 7), "ニュース (NHK)", font=font("bold", 24), fill=255)
    y += 60
    fnt, lh = font("regular", 21), 29
    for title in titles:
        lines = wrap(draw, title, fnt, W - 80)
        if y + lh * len(lines) > H - 15:
            break
        draw.text((30, y), "・", font=fnt, fill=0)
        for line in lines:
            draw.text((55, y), line, font=fnt, fill=0)
            y += lh
        y += 6


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "public/dashboard.png")
    now = datetime.now(JST)
    img = Image.new("L", (W, H), 255)
    draw = ImageDraw.Draw(img)

    # ヘッダー
    draw.text((30, 18), f"{now.month}月{now.day}日（{WEEKDAYS[now.weekday()]}）", font=font("bold", 40), fill=0)
    upd = f"更新 {now:%H:%M}"
    fu = font("regular", 20)
    draw.text((W - 30 - draw.textlength(upd, font=fu), 38), upd, font=fu, fill=80)
    draw.line((30, 85, W - 30, 85), fill=0, width=3)

    y = draw_weather(draw, now, 100)
    draw_news(draw, y)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, optimize=True)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
