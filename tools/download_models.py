"""Download pinned public model files and verify SHA-256 before installing them."""
import argparse
import hashlib
from pathlib import Path
import urllib.request

ZOO = '48b10fa505aeb51fbd127fc60a5c660040e823b7'
CLIP = 'd15189d7028b43f1d3e65039190477f6af591c2a'
FILES = [
    ('face_detection_yunet_2023mar.onnx', f'https://media.githubusercontent.com/media/opencv/opencv_zoo/{ZOO}/models/face_detection_yunet/face_detection_yunet_2023mar.onnx', '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'),
    ('face_recognition_sface_2021dec.onnx', f'https://media.githubusercontent.com/media/opencv/opencv_zoo/{ZOO}/models/face_recognition_sface/face_recognition_sface_2021dec.onnx', '0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79'),
    ('semantic/text_model_quantized.onnx', f'https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/{CLIP}/onnx/text_model_quantized.onnx', '73baab855d406190da9faa498cfedf65f15cf309f4cc7385b7b032e6d08e5c3a'),
    ('semantic/vision_model_quantized.onnx', f'https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/{CLIP}/onnx/vision_model_quantized.onnx', '583fd1110a514667812fee7d684952aaf82a99b959760c8d7dca7e0ab9839299'),
    ('semantic/tokenizer.json', f'https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/{CLIP}/tokenizer.json', 'f7f3b7af117d467b58374797691a6438d3e6b9e9cef800dfd5dced7f697a90cd'),
    ('semantic/preprocessor_config.json', f'https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/{CLIP}/preprocessor_config.json', '6f638fb9401a6d6296feff533ee7efe657b787c49f954f82f5906b36ef2a1b1f'),
]


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parents[1] / 'models')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    for name, url, expected in FILES:
        target = args.directory / name
        if target.is_file() and digest(target) == expected:
            print('Verified', name)
            continue
        if args.verify_only:
            raise SystemExit(f'Missing or incorrect checksum: {name}')
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + '.part')
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'SuperGallery-model-installer/2.4'})
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if digest(temporary) != expected:
                raise RuntimeError(f'Checksum mismatch: {name}; refusing to install')
            temporary.replace(target)
            print('Installed and verified', name)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
