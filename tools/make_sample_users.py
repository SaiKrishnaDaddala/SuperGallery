"""Multi-user fake NAS: Personal/<user>/... homes plus a Shared volume, with cross-user duplicates,
memes/forwards, screenshots, document photos and camera photos (with EXIF make)."""
import os
import random
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw

root = sys.argv[1] if len(sys.argv) > 1 else "sample_users"
here = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(root):
    shutil.rmtree(root)

# Each user gets the classic sample tree (duplicates, look-alikes, junk...).
for user in ("alice", "bob"):
    subprocess.run([sys.executable, os.path.join(here, "make_sample.py"), f"{root}/Personal/{user}"], check=True)
subprocess.run([sys.executable, os.path.join(here, "make_sample.py"), f"{root}/Shared/Family"], check=True)

r = random.Random(3)


def noisy(w, h, seed, colourful=True):
    rr = random.Random(seed)
    im = Image.new("RGB", (w, h), (rr.randint(0, 255), rr.randint(0, 255), rr.randint(0, 255)) if colourful else (245, 245, 240))
    d = ImageDraw.Draw(im)
    for _ in range(60):
        x, y = rr.randint(0, w), rr.randint(0, h)
        col = tuple(rr.randint(0, 255) for _ in range(3)) if colourful else (30, 30, 30)
        if colourful:
            d.ellipse([x, y, x + rr.randint(20, 300), y + rr.randint(20, 300)], fill=col)
        else:
            d.line([x, y, x + rr.randint(50, 400), y], fill=col, width=3)
    return im


for user in ("alice", "bob"):
    home = f"{root}/Personal/{user}"
    # camera photos with EXIF make
    os.makedirs(f"{home}/Camera", exist_ok=True)
    for i in range(6):
        im = noisy(2000, 1500, hash((user, i)) % 9999)
        ex = Image.Exif()
        ex[0x010F] = "Apple"
        im.save(f"{home}/Camera/IMG_{5000 + i}.jpg", quality=92, exif=ex)
    # WhatsApp memes / forwards
    os.makedirs(f"{home}/WhatsApp/Media/WhatsApp Images", exist_ok=True)
    for i in range(8):
        noisy(640, 640, 700 + i).save(f"{home}/WhatsApp/Media/WhatsApp Images/IMG-20240101-WA{i:04d}.jpg", quality=60)
    # phone screenshots
    os.makedirs(f"{home}/Pictures", exist_ok=True)
    for i in range(4):
        noisy(1170, 2532, 900 + i).save(f"{home}/Pictures/IMG_{7000 + i}.png")
    # document / receipt photos
    for i in range(3):
        noisy(1600, 2200, 300 + i, colourful=False).save(f"{home}/Pictures/receipt_{i}.jpg", quality=90)

# the same holiday video in both users' homes (cross-user duplicate, not a within-user duplicate)
shutil.copy(f"{root}/Personal/alice/Videos/holiday.mp4", f"{root}/Personal/bob/Videos/alice_holiday.mp4")
print("multi-user sample created at", os.path.abspath(root))
