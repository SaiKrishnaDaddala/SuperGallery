"""Create a fake NAS tree for local testing: duplicates, look-alike photos, junk, empty folders."""
import os
import random
import sys
import time

from PIL import Image, ImageDraw, ImageFilter

root = sys.argv[1] if len(sys.argv) > 1 else "sample_nas"
random.seed(7)


def mk(p, data=b""):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


def photo(seed, w=1600, h=1200):
    r = random.Random(seed)
    im = Image.new("RGB", (w, h), tuple(r.randint(0, 255) for _ in range(3)))
    d = ImageDraw.Draw(im)
    for _ in range(40):
        x, y = r.randint(0, w), r.randint(0, h)
        d.ellipse([x, y, x + r.randint(40, 500), y + r.randint(40, 400)], fill=tuple(r.randint(0, 255) for _ in range(3)))
    for _ in range(300):
        x, y = r.randint(0, w), r.randint(0, h)
        d.line([x, y, x + r.randint(-80, 80), y + r.randint(-80, 80)], fill=(r.randint(0, 255),) * 3, width=2)
    return im


for i in range(60):
    year = 2017 + i % 8
    im = photo(i)
    p = f"{root}/Photos/{year}/IMG_{1000 + i}.jpg"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    im.save(p, quality=90)
    t = time.mktime((year, 1 + i % 12, 1 + i % 27, 12, 0, 0, 0, 0, -1))
    os.utime(p, (t, t))
    if i % 3 == 0:  # exact duplicate in a backup folder
        q = f"{root}/Backup/Phone/IMG_{1000 + i}.jpg"
        mk(q, open(p, "rb").read())
    if i % 4 == 0:  # resized look-alike copy (smaller)
        q = f"{root}/WhatsApp/Images/IMG-WA{i:04d}.jpg"
        os.makedirs(os.path.dirname(q), exist_ok=True)
        im.resize((800, 600)).save(q, quality=70)
    if i % 10 == 0:  # blurry shot
        q = f"{root}/Photos/{year}/IMG_{1000 + i}_blur.jpg"
        im.filter(ImageFilter.GaussianBlur(14)).save(q, quality=85)

Image.new("RGB", (1200, 900), (3, 3, 4)).save(f"{root}/Photos/2020/pocket.jpg")
for i in range(5):
    Image.new("RGB", (64, 64), (i * 40, 90, 200)).save(f"{root}/Photos/icon_{i}.png")
os.makedirs(f"{root}/Photos/Screenshots", exist_ok=True)
photo(999, 1170, 2532).save(f"{root}/Photos/Screenshots/Screenshot_2023-01-01.png")

for i in range(30):
    mk(f"{root}/Documents/report_{i}.pdf", os.urandom(random.randint(20_000, 400_000)))
    mk(f"{root}/Documents/notes_{i}.txt", f"note {i}\n".encode() * 50)
blob = os.urandom(3_000_000)
for d in ("Downloads", "Backup/Old", "Documents/Archive"):
    mk(f"{root}/{d}/installer.iso", blob)
mk(f"{root}/Videos/holiday.mp4", os.urandom(8_000_000))
mk(f"{root}/Videos/holiday copy.mp4", open(f"{root}/Videos/holiday.mp4", "rb").read())
mk(f"{root}/Downloads/movie.mkv.part", os.urandom(500_000))
mk(f"{root}/Downloads/setup.exe", os.urandom(900_000))
mk(f"{root}/Photos/Thumbs.db", b"x" * 1000)
mk(f"{root}/Photos/2019/.DS_Store", b"x" * 600)
mk(f"{root}/Documents/._report_1.pdf", b"x" * 4096)
mk(f"{root}/Documents/empty.txt")
mk(f"{root}/Music/song.mp3", os.urandom(4_000_000))
mk(f"{root}/Logs/app.log", b"log line\n" * 20000)
for d in ("Empty/A/B", "Empty/C", "Projects/old/unused"):
    os.makedirs(f"{root}/{d}", exist_ok=True)
print("sample created at", os.path.abspath(root))
