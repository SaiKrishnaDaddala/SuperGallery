"""Inside the built image: make a short synthetic video, then probe it and grab a frame through app.media."""
import sys
import tempfile
from pathlib import Path

import av
import numpy as np

sys.path.insert(0, "/app")
from app import media  # noqa: E402

path = Path(tempfile.mkdtemp()) / "smoke.mp4"
with av.open(str(path), "w") as out:
    stream = out.add_stream("mpeg4", rate=10)
    stream.width, stream.height, stream.pix_fmt = 320, 240, "yuv420p"
    for i in range(40):
        pixels = np.full((240, 320, 3), (i * 6) % 255, dtype=np.uint8)
        for packet in stream.encode(av.VideoFrame.from_ndarray(pixels, format="rgb24")):
            out.mux(packet)
    for packet in stream.encode():
        out.mux(packet)

assert media.AVAILABLE, "PyAV is missing from the image"
width, height, duration = media.probe(str(path))
assert (width, height) == (320, 240) and 3.5 < duration < 4.5, (width, height, duration)
frame = media.frame(str(path), 3, 160)
assert frame is not None and frame.size == (160, 120), frame
assert media.probe("/nonexistent.mp4") is None and media.frame("/nonexistent.mp4", 0, 64) is None
print(f"Video probing and frame grabs work through PyAV {av.__version__}.")
