# Third-party notices

The application source is MIT licensed. That license does not replace the licenses of models, dependencies, icons or operating-system packages.

| Component | Source and license | Included material |
| --- | --- | --- |
| Lucide / Feather icons | [Lucide](https://github.com/lucide-icons/lucide), ISC; inherited Feather icons MIT | SVG paths adapted in `web/js/core.js`; full notice in `licenses/LUCIDE.txt` |
| YuNet detector | [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), MIT | Model downloaded during build; notice in `models/face_detection_yunet-LICENSE` |
| SFace embeddings | [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface), Apache-2.0 | Model downloaded during build; notice in `models/face_recognition_sface-LICENSE` |
| CLIP and ONNX conversion | [OpenAI CLIP](https://github.com/openai/CLIP), [Xenova model](https://huggingface.co/Xenova/clip-vit-base-patch32), MIT | Tokenizer/config included, quantized models downloaded; `models/semantic/LICENSE-CLIP.txt` |
| RapidOCR and PaddleOCR-derived OCR models | [RapidOCR](https://github.com/RapidAI/RapidOCR), [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR), Apache-2.0 | Installed through the pinned Python package; preserve its package notices when redistributing |
| FFmpeg | [FFmpeg licensing](https://ffmpeg.org/legal.html), license depends on build configuration | Installed from Debian when users build the image; Debian copyright notices remain under `/usr/share/doc` |
| Python dependencies | Individual projects listed in `requirements.txt` | Installed from their package distributions with their license metadata |

Model source revisions and SHA-256 checksums are recorded in `tools/download_models.py`. The release archives contain application source, notices and tokenizer metadata; they do not bundle ONNX weights, Python wheels or a prebuilt container image. The documented build obtains these from their upstream distributors. If you redistribute a built image, review and meet the license/source obligations for that image's exact components, including FFmpeg and codecs.

The conceptual cover artwork was generated for this project. It uses fictional media and contains no user library images. Apple and UGREEN names are used only to describe compatibility or design context; no endorsement is claimed.
