#!/usr/bin/env python3
"""
Live profile updater for github.com/mraadarshdubey
--------------------------------------------------
Regenerates on a schedule:
  * assets/footer.svg  -> Mumbai skyline reacting to LIVE weather (rain/sun/clouds/night)
  * README.md          -> time-aware greeting, live weather line, chai/uptime counters,
                          and an "AI thought of the day"

Pure standard library. No pip installs, no API keys required.
(Optionally uses ANTHROPIC_API_KEY for a real AI-written thought — falls back to a
 curated pool when the key is absent.)
"""

import json
import math
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "assets", "footer.template.svg")
FOOTER = os.path.join(ROOT, "assets", "footer.svg")
README = os.path.join(ROOT, "README.md")

IST = timezone(timedelta(hours=5, minutes=30))
MUMBAI = {"lat": 19.0760, "lon": 72.8777}
SHIPPING_SINCE = datetime(2023, 1, 1, tzinfo=IST)


# --------------------------------------------------------------------------- #
#  Weather
# --------------------------------------------------------------------------- #
def fetch_weather():
    """Return (category, temp_c, description) using Open-Meteo (no API key)."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={MUMBAI['lat']}&longitude={MUMBAI['lon']}"
        "&current=temperature_2m,weather_code,is_day&timezone=Asia%2FKolkata"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "profile-bot"})
        with urllib.request.urlopen(req, timeout=20) as r:
            cur = json.load(r)["current"]
        code = int(cur["weather_code"])
        temp = round(float(cur["temperature_2m"]))
        is_day = int(cur["is_day"]) == 1
    except Exception as e:  # network hiccup -> graceful default
        print(f"[weather] fallback ({e})")
        hour = datetime.now(IST).hour
        return ("clear", 29, "clear skies"), (6 <= hour < 19)

    if code in (95, 96, 99):
        cat, desc = "thunder", "thunderstorm"
    elif code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        cat, desc = "rain", "rain over Mumbai"
    elif code in (45, 48):
        cat, desc = "fog", "misty haze"
    elif code in (1, 2, 3):
        cat, desc = "clouds", "cloudy skies"
    else:
        cat, desc = "clear", "clear skies"
    return (cat, temp, desc), is_day


def weather_emoji(cat, is_day):
    return {
        "thunder": "⛈️",
        "rain": "🌧️",
        "fog": "🌫️",
        "clouds": "☁️",
        "clear": "☀️" if is_day else "🌙",
    }[cat]


def build_weather_svg(cat, is_day):
    """Return (sky_layer, foreground_layer) SVG snippets for the footer."""
    sky, fg = "", ""

    # --- sky tint / celestial body ---
    if cat == "clear" and is_day:
        sky += '<circle cx="800" cy="55" r="120" fill="url(#sunGlow)"/>'
        sky += '<circle cx="800" cy="55" r="16" fill="#FFD25A"/>'
        sky += ('<g stroke="#FFD25A" stroke-width="2" stroke-opacity="0.6" stroke-linecap="round">'
                '<animateTransform attributeName="transform" type="rotate" from="0 800 55" '
                'to="360 800 55" dur="40s" repeatCount="indefinite"/>')
        for ang in range(0, 360, 45):
            x1 = 800 + 22 * math.cos(math.radians(ang))
            y1 = 55 + 22 * math.sin(math.radians(ang))
            x2 = 800 + 32 * math.cos(math.radians(ang))
            y2 = 55 + 32 * math.sin(math.radians(ang))
            sky += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>'
        sky += "</g>"
    elif not is_day and cat in ("clear", "clouds", "fog"):
        # moon + extra stars for a crisp night
        sky += ('<circle cx="800" cy="52" r="15" fill="#EDEFF7"/>'
                '<circle cx="795" cy="48" r="15" fill="#0D0D1A"/>')
        for cx, cy, dur in [(150, 44, 3.1), (260, 34, 3.9), (480, 40, 2.7),
                            (610, 30, 4.2), (700, 60, 3.4), (380, 66, 3.6)]:
            sky += (f'<circle cx="{cx}" cy="{cy}" r="1.2" fill="#F5F5F0">'
                    f'<animate attributeName="opacity" values="0.2;1;0.2" dur="{dur}s" '
                    'repeatCount="indefinite"/></circle>')

    # --- clouds ---
    if cat in ("clouds", "rain", "thunder", "fog"):
        def cloud(x, y, s, op, dur, begin=0):
            g = (f'<g fill="#C9CEE0" fill-opacity="{op}" transform="translate({x},{y}) scale({s})">'
                 '<ellipse cx="0" cy="0" rx="26" ry="12"/><ellipse cx="20" cy="4" rx="20" ry="10"/>'
                 '<ellipse cx="-20" cy="4" rx="18" ry="9"/>'
                 f'<animateTransform attributeName="transform" additive="sum" type="translate" '
                 f'from="0 0" to="60 0" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/></g>')
            return g
        sky += cloud(180, 46, 1.0, 0.16, 26)
        sky += cloud(520, 34, 0.8, 0.13, 34, 4)
        sky += cloud(680, 58, 1.1, 0.18, 30, 2)

    # --- rain / thunder foreground ---
    if cat in ("rain", "thunder"):
        drops = ""
        # deterministic spread of raindrops
        for i in range(46):
            x = (i * 79 + 17) % 900
            dur = 0.55 + (i % 5) * 0.08
            begin = (i % 7) * 0.09
            drops += (
                f'<line x1="{x}" y1="-12" x2="{x-8}" y2="6" stroke="#9FC1FF" '
                f'stroke-width="1.1" stroke-opacity="0.55" stroke-linecap="round">'
                f'<animate attributeName="transform" attributeType="XML" type="translate" '
                f'from="0 0" to="-40 244" dur="{dur:.2f}s" begin="{begin:.2f}s" '
                'repeatCount="indefinite" additive="sum"/></line>'
            )
        fg += f'<g>{drops}</g>'

    if cat == "thunder":
        fg += ('<rect width="900" height="230" rx="16" fill="#EAF2FF" opacity="0">'
               '<animate attributeName="opacity" values="0;0;0.5;0;0.3;0" '
               'keyTimes="0;0.82;0.85;0.9;0.93;1" dur="6s" repeatCount="indefinite"/></rect>')

    # --- fog veil ---
    if cat == "fog":
        fg += ('<rect x="0" y="140" width="900" height="90" fill="#AEB6C8" opacity="0.12">'
               '<animate attributeName="opacity" values="0.08;0.2;0.08" dur="7s" '
               'repeatCount="indefinite"/></rect>')

    return sky, fg


# --------------------------------------------------------------------------- #
#  Greeting + counters + AI thought
# --------------------------------------------------------------------------- #
def greeting(now):
    h = now.hour
    if 5 <= h < 12:
        return "Good morning from Mumbai", "☀️"
    if 12 <= h < 17:
        return "Good afternoon from Mumbai", "🌤️"
    if 17 <= h < 21:
        return "Good evening from Mumbai", "🌆"
    return "Burning the midnight oil", "🌙"


AI_THOUGHTS = [
    "The best prompt is the one you didn't need — good UX makes AI invisible.",
    "Ship the model, then ship the guardrails. Never the other way round.",
    "An agent is only as smart as the tools you hand it.",
    "Latency is a feature. Users forgive wrong; they rarely forgive slow.",
    "RAG isn't magic — it's just giving the model a good memory.",
    "Every hallucination is a missing evaluation.",
    "Design for the model's confidence, not just its answer.",
    "Small models fine-tuned beat big models guessing.",
    "The interface is the moat, not the weights.",
    "Context windows grow; taste doesn't. Curate what you feed.",
    "Automate the boring 80%, keep the human in the delightful 20%.",
    "A chatbot that says 'I don't know' is worth more than one that lies.",
    "Prompt engineering is temporary; system design is forever.",
    "Vector search finds neighbours — you still decide who's family.",
    "The future isn't AI replacing devs. It's devs who wield AI replacing those who don't.",
    "Good AI feels like a fast intern. Great AI feels like a calm senior.",
    "Cache aggressively — tokens are money and patience.",
    "Tools > tokens. Give the model hands, not just a bigger mouth.",
    "Evals are the unit tests of the AI era.",
    "Make it work, make it grounded, then make it fast.",
    "The demo is easy. The edge cases are the product.",
    "Streaming responses aren't a nicety — they're respect for the user's time.",
    "If you can't measure the answer, you can't improve the prompt.",
    "Guard the output, not just the input.",
    "AI writes the code; you own the consequences. Review everything.",
]


def ai_thought(now):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        try:
            return _llm_thought(key), True
        except Exception as e:
            print(f"[ai] llm fallback ({e})")
    idx = now.timetuple().tm_yday % len(AI_THOUGHTS)
    return AI_THOUGHTS[idx], False


def _llm_thought(key):
    model = os.environ.get("AI_MODEL", "claude-3-5-haiku-latest")
    body = json.dumps({
        "model": model,
        "max_tokens": 60,
        "messages": [{
            "role": "user",
            "content": "Give me ONE short, punchy, original one-line thought (max 15 words) "
                       "about AI engineering or building intelligent products. No quotes, no preamble.",
        }],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.load(r)
    return data["content"][0]["text"].strip().strip('"')


# --------------------------------------------------------------------------- #
#  Writers
# --------------------------------------------------------------------------- #
def replace_block(text, name, content):
    pat = re.compile(f"(<!-- START:{name} -->).*?(<!-- END:{name} -->)", re.S)
    return pat.sub(lambda m: f"{m.group(1)}\n{content}\n{m.group(2)}", text)


def main():
    now = datetime.now(IST)
    (cat, temp, desc), is_day = fetch_weather()
    emoji = weather_emoji(cat, is_day)

    # ---- footer.svg ----
    sky, fg = build_weather_svg(cat, is_day)
    label = f"MUMBAI  ·  {emoji} {temp}°C  ·  {desc.upper()}  ·  LIVE"
    with open(TEMPLATE, encoding="utf-8") as f:
        svg = f.read()
    svg = (svg.replace("{{WEATHER_SKY}}", sky)
              .replace("{{WEATHER_FG}}", fg)
              .replace("{{WEATHER_LABEL}}", label))
    with open(FOOTER, "w", encoding="utf-8") as f:
        f.write(svg)

    # ---- README.md ----
    with open(README, encoding="utf-8") as f:
        md = f.read()

    g_text, g_emoji = greeting(now)
    live = (f"> {g_emoji} **{g_text}** &nbsp;·&nbsp; {emoji} {temp}°C, {desc} "
            f"&nbsp;·&nbsp; 🕐 {now.strftime('%I:%M %p')} IST")

    days = (now - SHIPPING_SINCE).days
    chai = days * 2
    counters = (f"`⏳ {days:,} days shipping` &nbsp; `☕ {chai:,} cups of chai` "
                f"&nbsp; `📍 Mumbai, IN` &nbsp; `🚀 always building`")

    thought, from_llm = ai_thought(now)
    tag = "🤖 AI-generated" if from_llm else "💡 curated"
    thought_md = f"> *\"{thought}\"*\n>\n> <sub>{tag} · refreshes daily</sub>"

    md = replace_block(md, "LIVE", live)
    md = replace_block(md, "COUNTERS", counters)
    md = replace_block(md, "AI_THOUGHT", thought_md)

    with open(README, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"[ok] {now:%Y-%m-%d %H:%M IST} | {cat} {temp}°C day={is_day} | "
          f"{days} days | thought_llm={from_llm}")


if __name__ == "__main__":
    main()
