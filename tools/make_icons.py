"""Render every SuperGallery icon from one SVG design: photos being filed into a folder.

    python tools/make_icons.py          # writes web/icons/*.svg and *.png (PNG needs Playwright + Edge/Chrome)
"""
import asyncio
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "web" / "icons"

ART = '''
  <path d="M96 168a24 24 0 0 1 24-24h76a24 24 0 0 1 18 8l18 20h104a24 24 0 0 1 24 24v24H96Z" fill="#fff" opacity=".38"/>
  <g transform="rotate(8 310 190)"><rect x="200" y="92" width="196" height="168" rx="22" fill="#fff" opacity=".6"/></g>
  <g transform="rotate(-9 240 180)">
    <rect x="128" y="70" width="228" height="196" rx="24" fill="#fff"/>
    <clipPath id="pic"><rect x="144" y="86" width="196" height="164" rx="12"/></clipPath>
    <g clip-path="url(#pic)">
      <rect x="144" y="86" width="196" height="164" fill="url(#sky)"/>
      <circle cx="298" cy="124" r="20" fill="#ffd23f"/>
      <path d="M144 212 198 150 236 188 268 160 340 222 340 250 144 250Z" fill="#2fb36b"/>
      <path d="M144 250 192 214 238 238 288 206 340 244 340 250Z" fill="#1f8a50"/>
    </g>
  </g>
  <path d="M86 238a22 22 0 0 1 22-22h296a22 22 0 0 1 22 22l-14 150a26 26 0 0 1-26 24H126a26 26 0 0 1-26-24Z" fill="url(#front)"/>
  <path d="M256 274c4 22 14 32 36 36-22 4-32 14-36 36-4-22-14-32-36-36 22-4 32-14 36-36Z" fill="#1675ea"/>
  <path d="M310 266c2 10 7 15 17 17-10 2-15 7-17 17-2-10-7-15-17-17 10-2 15-7 17-17Z" fill="#51a1ff"/>
'''

DEFS = '''<defs>
    <linearGradient id="tile" x1=".2" y1="0" x2=".8" y2="1"><stop offset="0" stop-color="#51a1ff"/><stop offset=".62" stop-color="#1675ea"/><stop offset="1" stop-color="#0058c4"/></linearGradient>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8fc9ff"/><stop offset="1" stop-color="#d9eeff"/></linearGradient>
    <linearGradient id="front" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#e3eeff"/></linearGradient>
  </defs>'''


def svg(rounded=True, scale=1.0):
    inset = (1 - scale) * 256
    tile = f'<rect width="512" height="512" rx="{115 if rounded else 0}" fill="url(#tile)"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">\n  {DEFS}\n  {tile}\n'
            f'  <g transform="translate({inset:.1f} {inset + 6 * scale:.1f}) scale({scale})">{ART}  </g>\n</svg>\n')


async def render(targets):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        for channel in ("msedge", "chrome"):
            try:
                browser = await p.chromium.launch(channel=channel)
                break
            except Exception:  # noqa: BLE001 - try the next installed browser
                continue
        page = await browser.new_page()
        for name, size, markup in targets:
            await page.set_viewport_size({"width": size, "height": size})
            await page.set_content(f'<style>html,body{{margin:0;background:transparent}}svg{{display:block;width:{size}px;height:{size}px}}</style>{markup}')
            await page.screenshot(path=str(OUT / name), omit_background=True)
        await browser.close()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "icon.svg").write_text(svg(), encoding="utf-8")
    full, safe = svg(rounded=False, scale=.92), svg(rounded=False, scale=.76)
    if "--svg-only" in sys.argv:
        return
    asyncio.run(render([
        ("icon-512.png", 512, svg()), ("icon-192.png", 192, svg()), ("favicon-32.png", 32, svg()),
        ("apple-touch-icon.png", 180, full), ("maskable-512.png", 512, safe), ("maskable-192.png", 192, safe),
    ]))
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
