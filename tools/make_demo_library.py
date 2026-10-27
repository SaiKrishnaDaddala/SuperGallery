"""Generate a realistic-looking demo NAS library for screenshots and manual testing.

Everything is synthetic: painted landscapes with camera EXIF dates, phone screenshots, receipts with
readable text, memes, duplicates, near-duplicates, short videos (if ffmpeg is installed) and documents.

    python tools/make_demo_library.py demo-library
    SCAN_ROOTS=demo-library/Personal,demo-library/Shared USERS_ROOT=demo-library/Personal ...
"""
import datetime as dt
import os
import random
import shutil
import subprocess
import sys
import zipfile
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = sys.argv[1] if len(sys.argv) > 1 else "demo-library"
W, H = 1600, 1066
FFMPEG = shutil.which("ffmpeg")

SKIES = {  # zenith, horizon, sun
    "dawn": ((88, 120, 196), (255, 196, 160), (255, 236, 200)),
    "noon": ((52, 128, 222), (184, 222, 250), (255, 252, 236)),
    "golden": ((70, 104, 170), (255, 178, 102), (255, 222, 150)),
    "dusk": ((40, 36, 92), (238, 120, 116), (255, 190, 150)),
    "night": ((8, 12, 34), (34, 50, 92), (232, 236, 255)),
}


def font(size, bold=False, mono=False):
    names = (["consola.ttf", "DejaVuSansMono.ttf"] if mono else
             ["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"])
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def vgrad(w, h, top, bottom, power=1.0):
    t = (np.linspace(0, 1, h) ** power)[:, None, None]
    arr = np.array(top)[None, None, :] * (1 - t) + np.array(bottom)[None, None, :] * t
    return Image.fromarray(np.repeat(arr, w, axis=1).astype("uint8"))


def ridge(rng, w, base, rough, steps=9):
    pts = [base + rng.uniform(-rough, rough), base + rng.uniform(-rough, rough)]
    amp = rough
    for _ in range(steps):
        nxt = []
        for a, b in zip(pts, pts[1:]):
            nxt += [a, (a + b) / 2 + rng.uniform(-amp, amp)]
        pts = nxt + [pts[-1]]
        amp *= 0.55
    xs = np.linspace(0, w, len(pts))
    return list(zip(xs, pts))


def sun(img, x, y, r, colour):
    glow = Image.new("RGB", img.size, (0, 0, 0))
    d = ImageDraw.Draw(glow)
    d.ellipse((x - r * 4, y - r * 4, x + r * 4, y + r * 4), fill=mix((0, 0, 0), colour, .35))
    glow = glow.filter(ImageFilter.GaussianBlur(r * 2))
    img = Image.fromarray(np.clip(np.asarray(img, dtype=np.int16) + np.asarray(glow, dtype=np.int16), 0, 255).astype("uint8"))
    ImageDraw.Draw(img).ellipse((x - r, y - r, x + r, y + r), fill=colour)
    return img


def mountains(rng, sky="noon", lake=False, trees=True, stars=False):
    zen, hor, sun_c = SKIES[sky]
    horizon = int(H * rng.uniform(.5, .62))
    img = vgrad(W, H, zen, hor, .8)
    if stars:
        d = ImageDraw.Draw(img)
        for _ in range(400):
            x, y, b = rng.randrange(W), rng.randrange(int(H * .55)), rng.randint(120, 255)
            d.point((x, y), fill=(b, b, b))
    img = sun(img, rng.randint(200, W - 200), int(horizon * rng.uniform(.35, .75)), rng.randint(26, 46), sun_c)
    d = ImageDraw.Draw(img)
    near = mix((20, 40, 34), zen, .15) if sky != "night" else (10, 14, 26)
    layers = 4
    for i in range(layers):
        t = i / (layers - 1)
        colour = mix(mix(hor, zen, .4), near, t ** 1.2)
        base = horizon - 160 + i * 70
        pts = ridge(rng, W, base, 140 - i * 22)
        d.polygon(pts + [(W, H), (0, H)], fill=colour)
        if trees and i == layers - 1:
            for _ in range(70):
                x = rng.randrange(W)
                y = min(p[1] for p in pts if abs(p[0] - x) < 30) + rng.randint(10, 90)
                h = rng.randint(30, 90)
                d.polygon([(x, y - h), (x - h * .28, y), (x + h * .28, y)], fill=mix(colour, (0, 0, 0), .25))
    if lake:
        top = int(H * .76)
        mirror = img.crop((0, top - (H - top), W, top)).transpose(Image.FLIP_TOP_BOTTOM).filter(ImageFilter.GaussianBlur(3))
        mirror = ImageEnhance.Brightness(mirror).enhance(.78)
        img.paste(mirror, (0, top))
        d = ImageDraw.Draw(img)
        for _ in range(60):
            y = rng.randint(top + 4, H)
            x = rng.randrange(W)
            d.line((x, y, x + rng.randint(30, 160), y), fill=mix(hor, (255, 255, 255), .3), width=1)
    return img


def beach(rng, sky="golden"):
    zen, hor, sun_c = SKIES[sky]
    horizon = int(H * .55)
    img = vgrad(W, horizon, zen, hor, .9)
    sea = vgrad(W, H - horizon, mix(hor, (20, 90, 140), .55), (16, 70, 112), .7)
    canvas = Image.new("RGB", (W, H))
    canvas.paste(img, (0, 0))
    canvas.paste(sea, (0, horizon))
    sx = rng.randint(400, W - 400)
    canvas = sun(canvas, sx, horizon - rng.randint(40, 140), 40, sun_c)
    d = ImageDraw.Draw(canvas)
    for i in range(90):
        y = horizon + 6 + int((i / 90) ** 1.6 * (H * .3))
        half = 10 + i * 2.2
        d.line((sx - half + rng.randint(-20, 20), y, sx + half + rng.randint(-20, 20), y), fill=mix(sun_c, hor, .3), width=2)
    sand = [(0, H)] + [(x, H * .82 + 40 * np.sin(x / 260 + rng.random() * 6)) for x in range(0, W + 40, 40)] + [(W, H)]
    d.polygon(sand, fill=(226, 196, 152))
    return canvas


def city(rng):
    img = vgrad(W, H, (20, 24, 60), (236, 130, 110), 1.2)
    d = ImageDraw.Draw(img)
    for layer, shade in ((0, (46, 44, 78)), (1, (24, 22, 42))):
        x = -20
        while x < W:
            bw, bh = rng.randint(60, 150), rng.randint(180, 620) - layer * 60
            d.rectangle((x, H - bh, x + bw, H), fill=shade)
            if layer:
                for wy in range(H - bh + 14, H - 10, 22):
                    for wx in range(x + 8, x + bw - 12, 18):
                        if rng.random() < .45:
                            d.rectangle((wx, wy, wx + 8, wy + 11), fill=rng.choice([(255, 214, 140), (255, 236, 190), (180, 210, 255)]))
            x += bw + rng.randint(4, 20)
    return img


def flowers(rng):
    img = vgrad(W, H, (34, 52, 30), (88, 122, 58), 1)
    bokeh = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(bokeh)
    for _ in range(40):
        x, y, r = rng.randrange(W), rng.randrange(H), rng.randint(20, 90)
        d.ellipse((x - r, y - r, x + r, y + r), fill=rng.choice([(90, 120, 40), (140, 160, 60), (200, 190, 120)]))
    img = Image.blend(img, bokeh.filter(ImageFilter.GaussianBlur(30)), .45)
    d = ImageDraw.Draw(img)
    petal = rng.choice([(250, 250, 250), (246, 170, 196), (255, 214, 92), (186, 150, 255)])
    for _ in range(rng.randint(3, 6)):
        cx, cy, r = rng.randint(200, W - 200), rng.randint(200, H - 200), rng.randint(60, 140)
        d.line((cx, cy, cx + rng.randint(-60, 60), H), fill=(52, 96, 40), width=8)
        for k in range(10):
            a = k / 10 * 2 * np.pi
            px, py = cx + np.cos(a) * r * .55, cy + np.sin(a) * r * .55
            d.ellipse((px - r * .42, py - r * .42, px + r * .42, py + r * .42), fill=mix(petal, (255, 255, 255), rng.random() * .2))
        d.ellipse((cx - r * .26, cy - r * .26, cx + r * .26, cy + r * .26), fill=(244, 186, 40))
    return img


def aurora(rng):
    img = mountains(rng, "night", lake=rng.random() < .5, stars=True)
    band = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(band)
    for k in range(3):
        y0 = rng.randint(120, 360)
        pts = [(x, y0 + 80 * np.sin(x / 300 + k)) for x in range(0, W + 50, 50)]
        d.line(pts, fill=rng.choice([(60, 255, 160), (90, 220, 255), (170, 120, 255)]), width=70)
    return Image.fromarray(np.clip(np.asarray(img, dtype=np.int16) + (np.asarray(band.filter(ImageFilter.GaussianBlur(40)), dtype=np.int16) * .7).astype(np.int16), 0, 255).astype("uint8"))


SCENES = [
    lambda r: mountains(r, "noon", lake=True), lambda r: mountains(r, "golden"), lambda r: mountains(r, "dawn", lake=True),
    lambda r: mountains(r, "dusk"), lambda r: beach(r, "golden"), lambda r: beach(r, "noon"), lambda r: beach(r, "dusk"),
    city, flowers, aurora,
]


def grain(img, seed, sigma=7.0):
    noise = np.random.default_rng(seed).normal(0, sigma, (img.height, img.width, 1))
    return Image.fromarray(np.clip(np.asarray(img, dtype=np.float32) + noise, 0, 255).astype("uint8"))


def save_photo(img, path, when, model="iPhone 15 Pro", quality=88, blurry=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = img.filter(ImageFilter.GaussianBlur(7)) if blurry else grain(img, zlib.crc32(path.encode()))
    ex = Image.Exif()
    ex[0x010F], ex[0x0110] = ("Apple" if "iPhone" in model else "Sony"), model
    stamp = when.strftime("%Y:%m:%d %H:%M:%S")
    ex[0x0132] = stamp
    ex.get_ifd(0x8769)[0x9003] = stamp
    img.save(path, quality=quality, exif=ex)
    os.utime(path, (when.timestamp(), when.timestamp()))


def phone_screenshot(rng, kind):
    w, h = 1170, 2532
    img = Image.new("RGB", (w, h), (242, 242, 247) if kind != "music" else (24, 24, 30))
    d = ImageDraw.Draw(img)
    fg = (0, 0, 0) if kind != "music" else (255, 255, 255)
    d.text((80, 50), "9:41", font=font(46, True), fill=fg)
    if kind == "chat":
        d.rectangle((0, 140, w, 300), fill=(250, 250, 252))
        d.text((w // 2 - 120, 190), "Family", font=font(54, True), fill=(0, 0, 0))
        y = 360
        for i, msg in enumerate(["Did the photos from the trip upload?", "Yes! All on the NAS now", "Can you find the one at the lake?",
                                 "Search 'lake' in SuperGallery", "Found it, thanks!", "Dinner at 8?", "Perfect"]):
            mine = i % 2 == 1
            tw = d.textlength(msg, font=font(44))
            x0 = w - tw - 140 if mine else 60
            d.rounded_rectangle((x0, y, x0 + tw + 80, y + 110), 50, fill=(10, 132, 255) if mine else (229, 229, 234))
            d.text((x0 + 40, y + 30), msg, font=font(44), fill=(255, 255, 255) if mine else (0, 0, 0))
            y += 160
    elif kind == "settings":
        d.text((60, 180), "Settings", font=font(84, True), fill=(0, 0, 0))
        y = 340
        for label in ["Wi-Fi", "Bluetooth", "Mobile Service", "Notifications", "Sounds & Haptics", "Focus", "Screen Time", "General", "Display & Brightness", "Wallpaper", "Battery", "Privacy & Security"]:
            d.rounded_rectangle((40, y, w - 40, y + 130), 26, fill=(255, 255, 255))
            d.rounded_rectangle((80, y + 30, 150, y + 100), 16, fill=rng.choice([(10, 132, 255), (52, 199, 89), (255, 149, 0), (255, 59, 48), (88, 86, 214)]))
            d.text((190, y + 40), label, font=font(48), fill=(0, 0, 0))
            y += 150
    else:
        art = rng.choice(SCENES)(rng).resize((900, 600)).crop((150, 0, 750, 600)).resize((900, 900))
        img.paste(art, (135, 360))
        d.text((135, 1340), "Mountain Morning", font=font(64, True), fill=fg)
        d.text((135, 1430), "The Demo Band", font=font(48), fill=(160, 160, 170))
        d.rounded_rectangle((135, 1580, w - 135, 1594), 7, fill=(80, 80, 90))
        d.rounded_rectangle((135, 1580, 600, 1594), 7, fill=fg)
    return img


def receipt(rng, store):
    paper = Image.new("RGB", (900, 1500), (250, 249, 244))
    d = ImageDraw.Draw(paper)
    y = 70
    d.text((450, y), store.upper(), font=font(52, True, mono=True), fill=(30, 30, 30), anchor="mt")
    y += 90
    d.text((450, y), "12 Market Street  ·  Tel 555-0142", font=font(28, mono=True), fill=(70, 70, 70), anchor="mt")
    y += 90
    total = 0
    for item in rng.sample(["Milk 1L", "Sourdough bread", "Bananas", "Coffee beans", "Eggs x12", "Tomatoes", "Pasta",
                            "Olive oil", "Cheddar", "Apples", "Rice 2kg", "Yoghurt", "Batteries AA", "USB-C cable"], 8):
        price = rng.randint(80, 1400) / 100
        total += price
        d.text((70, y), item, font=font(34, mono=True), fill=(30, 30, 30))
        d.text((830, y), f"{price:6.2f}", font=font(34, mono=True), fill=(30, 30, 30), anchor="ra")
        y += 60
    d.line((70, y + 10, 830, y + 10), fill=(60, 60, 60), width=2)
    d.text((70, y + 40), "TOTAL", font=font(44, True, mono=True), fill=(10, 10, 10))
    d.text((830, y + 40), f"{total:6.2f}", font=font(44, True, mono=True), fill=(10, 10, 10), anchor="ra")
    d.text((450, y + 160), "THANK YOU FOR SHOPPING", font=font(30, mono=True), fill=(70, 70, 70), anchor="mt")
    photo = vgrad(1600, 2100, (92, 64, 44), (60, 40, 28))
    paper = paper.rotate(rng.uniform(-4, 4), expand=True, fillcolor=(0, 0, 0, 0)) if False else paper
    photo.paste(paper, (350, 300))
    return photo


def meme(rng, top, bottom):
    img = rng.choice(SCENES)(rng).resize((1600, 1066)).crop((267, 0, 1333, 1066)).resize((1080, 1080))
    d = ImageDraw.Draw(img)
    for text, y in ((top, 40), (bottom, 1040)):
        f = font(76, True)
        d.text((540, y), text.upper(), font=f, fill="white", stroke_width=5, stroke_fill="black", anchor="mt" if y < 500 else "mb")
    return img


def video(src, dest, when):
    if not FFMPEG:
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-loop", "1", "-i", src, "-vf",
                    "scale=1920:1280,zoompan=z='min(zoom+0.0012,1.15)':d=125:s=1280x720:fps=25,format=yuv420p",
                    "-t", "5", "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", dest], check=True)
    os.utime(dest, (when.timestamp(), when.timestamp()))


def pdf(path, title, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    page = Image.new("RGB", (1240, 1754), "white")
    d = ImageDraw.Draw(page)
    d.text((100, 120), title, font=font(56, True), fill=(20, 20, 20))
    for i, line in enumerate(lines):
        d.text((100, 260 + i * 56), line, font=font(34), fill=(50, 50, 50))
    page.save(path, "PDF", resolution=150)


def build():
    if os.path.exists(ROOT):
        shutil.rmtree(ROOT)
    rng = random.Random(2024)
    start = dt.datetime(2024, 1, 6, 9, 0)
    people = {"alex": 70, "sam": 40}
    for user, count in people.items():
        home = f"{ROOT}/Personal/{user}"
        trips = ["Iceland 2024", "Goa 2025", "Swiss Alps", "Lisbon weekend"]
        made = []
        for i in range(count):
            when = start + dt.timedelta(days=rng.randint(0, 700), hours=rng.randint(0, 11), minutes=rng.randint(0, 59))
            folder = f"Trips/{rng.choice(trips)}" if rng.random() < .45 else f"Camera Roll/{when:%Y}"
            path = f"{home}/Photos/{folder}/IMG_{4100 + i:04d}.jpg"
            img = rng.choice(SCENES)(random.Random(rng.random()))
            save_photo(img, path, when, model=rng.choice(["iPhone 15 Pro", "iPhone 13", "ILCE-7M4"]), blurry=i % 23 == 5)
            made.append((path, img, when))
        # Bursts: near-identical frames for "similar photos".
        for k, (path, img, when) in enumerate(rng.sample(made, 6)):
            for j in range(1, rng.randint(2, 4)):
                shifted = ImageEnhance.Brightness(img.crop((j * 14, j * 9, W - j * 6, H - j * 4)).resize((W, H))).enhance(1 + j * .04)
                save_photo(shifted, path.replace(".jpg", f"_{j}.jpg"), when + dt.timedelta(seconds=j))
        # Exact duplicates from an old phone backup.
        for path, _, when in rng.sample(made, 10):
            dest = f"{home}/Backups/Phone backup 2024/{os.path.basename(path)}"
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(path, dest)
        # Screenshots, memes, receipts, videos, documents.
        for i, kind in enumerate(["chat", "settings", "music", "chat", "settings", "music"][: 6 if user == "alex" else 3]):
            when = start + dt.timedelta(days=rng.randint(0, 700))
            p = f"{home}/Photos/Screenshots/Screenshot_{when:%Y-%m-%d}-{10 + i}-{rng.randint(10, 59)}-{rng.randint(10, 59)}.png"
            os.makedirs(os.path.dirname(p), exist_ok=True)
            phone_screenshot(random.Random(i * 7 + len(user)), kind).save(p)
            os.utime(p, (when.timestamp(), when.timestamp()))
        jokes = [("me after", "deleting 4,000 duplicates"), ("one does not simply", "remember where the photo is"),
                 ("my NAS", "at 3am indexing everything"), ("when the backup", "finally finishes"), ("nobody:", "my phone: 9 copies of one photo")]
        for i, (top, bottom) in enumerate(jokes[: 5 if user == "alex" else 3]):
            p = f"{home}/WhatsApp/Media/WhatsApp Images/IMG-2025{i + 1:02d}{10 + i}-WA00{i:02d}.jpg"
            os.makedirs(os.path.dirname(p), exist_ok=True)
            meme(random.Random(i + 40), top, bottom).save(p, quality=55)
            when = start + dt.timedelta(days=rng.randint(0, 700))
            os.utime(p, (when.timestamp(), when.timestamp()))
        for i, store in enumerate(["Green Grocer", "Corner Market", "City Hardware"][: 3 if user == "alex" else 1]):
            when = start + dt.timedelta(days=rng.randint(0, 700))
            save_photo(receipt(random.Random(i + 9), store), f"{home}/Documents/Receipts/receipt_{when:%Y%m%d}.jpg", when)
        for i, (path, _, when) in enumerate(rng.sample(made, 3 if user == "alex" else 2)):
            video(path, f"{home}/Videos/VID_{when:%Y%m%d}_{i}.mp4", when)
        pdf(f"{home}/Documents/Insurance/home-insurance-2025.pdf", "Home insurance summary",
            ["Policy: DEMO-0000-1234", "Cover: contents and accidental damage", "Renewal: 1 March 2026", "This is sample data."])
        pdf(f"{home}/Documents/Manuals/nas-quick-start.pdf", "NAS quick start",
            ["1. Connect power and network", "2. Open the web portal", "3. Create a storage pool", "4. Install Docker"])
        os.makedirs(f"{home}/Documents/Notes", exist_ok=True)
        with open(f"{home}/Documents/Notes/packing-list.txt", "w") as f:
            f.write("Passport\nCharger\nCamera + spare battery\nHiking boots\nRain jacket\n")
        with open(f"{home}/Documents/budget-2025.csv", "w") as f:
            f.write("month,groceries,travel,utilities\n" + "".join(f"{m},{rng.randint(200, 400)},{rng.randint(0, 900)},{rng.randint(90, 160)}\n" for m in range(1, 13)))
        with zipfile.ZipFile(f"{home}/Documents/old-projects.zip", "w") as z:
            z.writestr("readme.txt", "Archived sample project\n")
    # Shared family album, partly duplicating Alex's trip photos.
    fam = f"{ROOT}/Shared/Family"
    alex_photos = [os.path.join(dp, f) for dp, _, fs in os.walk(f"{ROOT}/Personal/alex/Photos/Trips") for f in fs]
    for p in rng.sample(alex_photos, min(8, len(alex_photos))):
        dest = f"{fam}/Holidays/{os.path.basename(p)}"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(p, dest)
    for i in range(18):
        when = start + dt.timedelta(days=rng.randint(0, 700))
        save_photo(rng.choice(SCENES)(random.Random(rng.random())), f"{fam}/Family Album/{when:%Y}/DSC0{2200 + i}.jpg", when, model="ILCE-7M4")
    print("demo library created at", os.path.abspath(ROOT))


if __name__ == "__main__":
    build()
