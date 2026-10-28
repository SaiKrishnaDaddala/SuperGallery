"""Standalone video helper, started by app.media in its own process with a time limit.

    python -I media_worker.py probe <path>                 -> JSON {"width", "height", "duration"}
    python -I media_worker.py frame <path> <seconds> <fit>  -> JPEG of the first frame at or after <seconds>

A damaged or hostile file can only crash or stall this short-lived process, never the server.
It imports nothing from the app so it can run isolated (-I).
"""
import io
import json
import sys

import av
from PIL import Image

THREADS = 2


def _video(container):
    stream = container.streams.video[0]
    stream.codec_context.thread_count = THREADS
    stream.thread_type = "AUTO"
    return stream


def probe(path):
    with av.open(path) as container:
        stream = container.streams.video[0] if container.streams.video else None
        duration = container.duration / av.time_base if container.duration else None
        if not duration and stream is not None and stream.duration and stream.time_base:
            duration = float(stream.duration * stream.time_base)
        return {"width": stream.codec_context.width or None if stream is not None else None,
                "height": stream.codec_context.height or None if stream is not None else None,
                "duration": duration or None}


def frame(path, seconds, fit):
    with av.open(path) as container:
        if not container.streams.video:
            return b""
        stream = _video(container)
        if seconds > 0 and stream.time_base:
            container.seek(int(seconds / stream.time_base), stream=stream, backward=True, any_frame=False)
        for decoded in container.decode(stream):
            if decoded.time is not None and decoded.time < seconds - 0.05:
                continue
            image = decoded.to_image()
            # Phones store portrait video sideways plus a rotation; apply it like the ffmpeg CLI does.
            rotation = int(round(decoded.rotation or 0)) % 360
            if rotation:
                image = image.rotate(rotation, expand=True)
            image.thumbnail((fit, fit))
            out = io.BytesIO()
            image.convert("RGB").save(out, "JPEG", quality=90)
            return out.getvalue()
    return b""


def main(argv):
    command, path = argv[1], argv[2]
    if command == "probe":
        sys.stdout.write(json.dumps(probe(path)))
    elif command == "frame":
        sys.stdout.buffer.write(frame(path, float(argv[3]), int(argv[4])))
    else:
        raise SystemExit(f"unknown command {command}")


if __name__ == "__main__":
    av.logging.set_level(av.logging.ERROR)
    main(sys.argv)
