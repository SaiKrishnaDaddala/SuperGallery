# Local visual search

CLIP ViT-B/32, quantized ONNX export by Xenova (Hugging Face).
Source: https://huggingface.co/Xenova/clip-vit-base-patch32
Pinned revision: d15189d7028b43f1d3e65039190477f6af591c2a
Base model: https://huggingface.co/openai/clip-vit-base-patch32
License: MIT; see LICENSE-CLIP.txt. SHA256SUMS.json records downloaded artifacts;
the runtime verifies model and tokenizer hashes against constants before loading.

Images and queries are processed on the NAS. The runtime does not download models
or send images, embeddings or searches to a service. Best suited to English scene
descriptions. Results are approximate similarities, not verified facts or identities.
Small actions, counts, negation, handwriting and complex relationships may be missed.
