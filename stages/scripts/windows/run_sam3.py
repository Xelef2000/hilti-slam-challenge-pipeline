#!/usr/bin/env python3
"""Run SAM3 segmentation from GroundingDINO boxes."""

from __future__ import annotations

import json
import os
import sys
from contextlib import nullcontext
from pathlib import Path

import matplotlib
import numpy as np
import torch
from PIL import Image

matplotlib.use("Agg")
import matplotlib.pyplot as plt

WINDOWS_PIPELINE_ROOT = Path(
    os.environ.get("WINDOWS_PIPELINE_ROOT", "/opt/windows_pipeline")
)
SAM3_ROOT = WINDOWS_PIPELINE_ROOT / "sam3"
sys.path.insert(0, str(SAM3_ROOT))

from sam3.model.sam3_image_processor import Sam3Processor  # noqa: E402
from sam3.model_builder import build_sam3_image_model  # noqa: E402


def crop_center_band(image: Image.Image) -> Image.Image:
    width, height = image.size
    left = int(width * 0.25)
    right = int(width * 0.75)
    result = Image.new(image.mode, (width, height), (0, 0, 0))
    result.paste(image.crop((left, 0, right, height)), (left, 0))
    return result


def filter_boxes(boxes: np.ndarray) -> list[np.ndarray]:
    filtered: list[np.ndarray] = []
    for box in boxes:
        if box[2] > 0.6 or box[3] > 0.6:
            continue
        if box[2] < 0.025 or box[3] < 0.025:
            continue
        duplicate = any(np.linalg.norm(box[:2] - accepted[:2]) < 0.05 for accepted in filtered)
        if not duplicate:
            filtered.append(box)
    return filtered


def save_visualization(image: Image.Image, masks: torch.Tensor, output_path: Path, masks_path: Path) -> None:
    plt.figure(figsize=(12, 8))
    plt.imshow(image)
    mask_img = np.zeros((image.size[1], image.size[0], 3), dtype=np.uint8)

    masks_np = masks.cpu().float().numpy()
    if masks_np.ndim == 4:
        masks_np = masks_np.squeeze(1)

    for index, mask in enumerate(masks_np):
        mask_binary = (mask > 0.5).astype(np.uint8)
        color = np.concatenate([plt.cm.tab10(index % 10)[:3], [0.5]])
        height, width = mask_binary.shape
        overlay = mask_binary.reshape(height, width, 1) * color.reshape(1, 1, -1)
        plt.gca().imshow(overlay)
        mask_img += mask_binary.reshape(height, width, 1) * 255

    plt.axis("off")
    plt.savefig(output_path, bbox_inches="tight", pad_inches=0)
    plt.close()
    np.save(masks_path, mask_img)


def main() -> int:
    args = json.loads(sys.argv[1])
    image_path = Path(args["image_path"])
    boxes_path = Path(args["boxes_path"])
    checkpoint_path = args.get("checkpoint_path", "")
    device = args["device"]
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Requested CUDA for SAM3 but no GPU is available.")

    image = crop_center_band(Image.open(image_path).convert("RGB"))
    boxes = np.load(boxes_path).astype(np.float32)
    filtered_boxes = filter_boxes(boxes)
    print(f"[window_sam] Device: {device}")
    print(f"[window_sam] Filtered boxes: {len(filtered_boxes)}")

    hf_token = os.environ.get("HF_TOKEN", "").strip()
    if checkpoint_path:
        model = build_sam3_image_model(
            device=device,
            checkpoint_path=checkpoint_path,
            load_from_HF=False,
        )
    elif hf_token:
        model = build_sam3_image_model(device=device)
    else:
        raise RuntimeError(
            "SAM3 requires either --sam3-checkpoint pointing to a local checkpoint "
            "or HF_TOKEN in the environment for the gated Hugging Face model."
        )
    processor = Sam3Processor(model, device=device)
    inference_state = processor.set_image(image)
    processor.reset_all_prompts(inference_state)
    for box in filtered_boxes:
        processor.add_geometric_prompt(box=box.tolist(), label=True, state=inference_state)

    autocast_context = (
        torch.autocast(device_type="cuda", dtype=torch.bfloat16)
        if device == "cuda"
        else nullcontext()
    )
    with autocast_context:
        output = processor._forward_grounding(state=inference_state)

    output_path = image_path.parent / "windows_segmented.png"
    masks_path = image_path.parent / "windows_masks.npy"
    save_visualization(image, output["masks"], output_path, masks_path)
    print(f"[window_sam] Output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
