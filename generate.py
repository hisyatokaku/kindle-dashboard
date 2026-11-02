"""Kindle 用ダッシュボード画像 (600x800 グレースケール PNG) を生成する。

天気: Open-Meteo / ニュース: NHK RSS
使い方: python generate.py [出力パス]  (既定: public/dashboard.png)

レイアウト (上から): 日付 / 現在の天気 (大) / 3時間ごと / 明日 / ニュース 3件
天気は文字ではなく描画したアイコンで示す。
"""
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 600, 800
M = 32  # 左右の余白
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
NEWS_COUNT = 3

# 濃淡 (E-ink は 16 階調)
INK, SUB, RULE, CLOUD, PAPER = 0, 90, 170, 200, 255

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
WEEKDAYS = "月火水木金土日"


def font(weight, size):
    for path in FONT_CANDIDATES[weight]:
        if Path(path).exists():
            return ImageFont.truetype(path, size, index=0)  # Noto CJK の index 0 は JP
    raise FileNotFoundError(f"日本語フォントが見つかりません: {weight}")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "kindle-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


# ---------- 天気アイコン ----------

def kind(code):
    """WMO 天気コード → アイコンの種類"""
    if code <= 1:
        return "sun"
    if code == 2:
        return "partly"
    if code == 3:
        return "cloud"
    if code in (45, 48):
        return "fog"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code >= 95:
        return "thunder"
    return "rain"


def _sun(d, cx, cy, s):
    r = s * 0.2
    w = max(2, round(s * 0.05))
    for i in range(8):
        v = [(1, 0), (0.7071, 0.7071), (0, 1), (-0.7071, 0.7071)][i % 4]
        sign = 1 if i < 4 else -1
        x1, y1 = cx + sign * v[0] * r * 1.45, cy + sign * v[1] * r * 1.45
        x2, y2 = cx + sign * v[0] * r * 2.05, cy + sign * v[1] * r * 2.05
        d.line((x1, y1, x2, y2), fill=INK, width=w)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=INK, width=w, fill=PAPER)


def _cloud(d, cx, cy, s):
    w = max(2, round(s * 0.045))

    def shape(inset, fill):
        parts = [
            (cx - s * 0.26, cy + s * 0.02, s * 0.17),
            (cx - s * 0.02, cy - s * 0.08, s * 0.24),
            (cx + s * 0.24, cy + s * 0.04, s * 0.15),
        ]
        for x, y, r in parts:
            r -= inset
            d.ellipse((x - r, y - r, x + r, y + r), fill=fill)
        d.rounded_rectangle(
            (cx - s * 0.42 + inset, cy + s * 0.02 + inset, cx + s * 0.39 - inset, cy + s * 0.19 - inset),
            radius=s * 0.085, fill=fill,
        )

    shape(0, INK)
    shape(w, CLOUD)


def draw_icon(d, code, cx, cy, s):
    """(cx, cy) を中心に一辺 s の天気アイコンを描く"""
    k = kind(code)
    w = max(2, round(s * 0.045))
    if k == "sun":
        _sun(d, cx, cy, s * 1.1)
        return
    if k == "partly":
        _sun(d, cx - s * 0.16, cy - s * 0.16, s * 0.85)
        _cloud(d, cx + s * 0.06, cy + s * 0.1, s * 0.85)
        return
    # 雲を少し上に置き、下に降水などを描く
    oy = 0 if k == "cloud" else -s * 0.12
    _cloud(d, cx, cy + oy, s)
    base = cy + oy + s * 0.27
    if k == "rain":
        for dx in (-0.2, 0, 0.2):
            x = cx + s * dx
            d.line((x + s * 0.05, base, x - s * 0.03, base + s * 0.18), fill=INK, width=w)
    elif k == "snow":
        for dx in (-0.2, 0, 0.2):
            x, y, r = cx + s * dx, base + s * 0.09, s * 0.045
            d.ellipse((x - r, y - r, x + r, y + r), fill=INK)
    elif k == "fog":
        for i in range(2):
            y = base + s * 0.04 + i * s * 0.1
            d.line((cx - s * 0.32, y, cx + s * 0.32, y), fill=INK, width=w)
    elif k == "thunder":
        x, y = cx, base
        d.polygon([
            (x + s * 0.04, y), (x - s * 0.08, y + s * 0.13), (x, y + s * 0.13),
            (x - s * 0.06, y + s * 0.26), (x + s * 0.1, y + s * 0.09), (x + s * 0.02, y + s * 0.09),
        ], fill=INK)


# ---------- 描画 ----------

def text_right(d, x, y, s, fnt, fill=INK):
    d.text((x - d.textlength(s, font=fnt), y), s, font=fnt, fill=fill)


def text_center(d, cx, y, s, fnt, fill=INK):
    d.text((cx - d.textlength(s, font=fnt) / 2, y), s, font=fnt, fill=fill)


def ellipsize(d, s, fnt, width):
    if d.textlength(s, font=fnt) <= width:
        return s
    while s and d.textlength(s + "…", font=fnt) > width:
        s = s[:-1]
    return s + "…"


def section_label(d, y, label):
    d.text((M, y), label, font=font("bold", 18), fill=SUB)


def draw_header(d, now):
    d.text((M, 22), f"{now.month}月{now.day}日", font=font("bold", 44), fill=INK)
    x = M + d.textlength(f"{now.month}月{now.day}日", font=font("bold", 44)) + 12
    d.text((x, 38), f"{WEEKDAYS[now.weekday()]}曜日", font=font("regular", 26), fill=INK)
    text_right(d, W - M, 44, f"{now:%H:%M} 更新", font("regular", 18), SUB)
    d.line((M, 96, W - M, 96), fill=INK, width=3)


def draw_now(d, w, y):
    cur, daily = w["current"], w["daily"]
    draw_icon(d, cur["weather_code"], M + 90, y + 95, 170)
    text_right(d, W - M, y - 8, f"{round(cur['temperature_2m'])}°", font("bold", 120))
    hi, lo = round(daily["temperature_2m_max"][0]), round(daily["temperature_2m_min"][0])
    text_right(d, W - M, y + 150, f"最高 {hi}°  最低 {lo}°", font("regular", 24))
    text_right(d, W - M, y + 183, f"降水 {daily['precipitation_probability_max'][0]}%", font("regular", 24))
    return y + 220


def draw_hourly(d, w, now, y):
    d.line((M, y, W - M, y), fill=RULE, width=1)
    section_label(d, y + 12, "3時間ごと")
    h = w["hourly"]
    times = h["time"]
    # 現在より後で 3 の倍数の時刻から 5 枠
    first = next(i for i, t in enumerate(times) if t > now.strftime("%Y-%m-%dT%H:%M") and int(t[11:13]) % 3 == 0)
    colw = (W - 2 * M) / 5
    f_time, f_temp, f_rain = font("regular", 20), font("bold", 28), font("regular", 18)
    for k in range(5):
        i = first + 3 * k
        cx = M + colw * (k + 0.5)
        text_center(d, cx, y + 45, f"{int(times[i][11:13])}時", f_time)
        draw_icon(d, h["weather_code"][i], cx, y + 112, 64)
        text_center(d, cx, y + 150, f"{round(h['temperature_2m'][i])}°", f_temp)
        text_center(d, cx, y + 188, f"{h['precipitation_probability'][i]}%", f_rain, SUB)
    return y + 218


def draw_tomorrow(d, w, y):
    d.line((M, y, W - M, y), fill=RULE, width=1)
    daily = w["daily"]
    d.text((M, y + 26), "明日", font=font("bold", 28), fill=INK)
    draw_icon(d, daily["weather_code"][1], M + 125, y + 46, 56)
    hi, lo = round(daily["temperature_2m_max"][1]), round(daily["temperature_2m_min"][1])
    d.text((M + 175, y + 24), f"{hi}°", font=font("bold", 32), fill=INK)
    d.text((M + 240, y + 31), f"/ {lo}°", font=font("regular", 24), fill=INK)
    text_right(d, W - M, y + 31, f"降水 {daily['precipitation_probability_max'][1]}%", font("regular", 24))
    return y + 88


def draw_news(d, y):
    d.line((M, y, W - M, y), fill=RULE, width=1)
    section_label(d, y + 12, "ニュース")
    root = ET.fromstring(fetch(NEWS_URL))
    titles = [i.findtext("title", "").strip() for i in root.iter("item")][:NEWS_COUNT]
    fnt = font("regular", 21)
    y += 46
    for t in titles:
        d.text((M, y), ellipsize(d, t, fnt, W - 2 * M), font=fnt, fill=INK)
        y += 34


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "public/dashboard.png")
    now = datetime.now(JST)
    img = Image.new("L", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    w = json.loads(fetch(WEATHER_URL))
    draw_header(d, now)
    y = draw_now(d, w, 110)
    y = draw_hourly(d, w, now, y)
    y = draw_tomorrow(d, w, y)
    draw_news(d, y)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, optimize=True)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
