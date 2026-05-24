#!/usr/bin/env python3
"""Run GroundingDINO on a single image."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

WINDOWS_PIPELINE_ROOT = Path(
    os.environ.get("WINDOWS_PIPELINE_ROOT", "/opt/windows_pipeline")
)
GROUNDING_DINO_ROOT = WINDOWS_PIPELINE_ROOT / "GroundingDINO"
GROUNDING_DINO_CHECKPOINT_URL = (
    "https://github.com/IDEA-Research/GroundingDINO/releases/download/"
    "v0.1.0-alpha/groundingdino_swint_ogc.pth"
)
sys.path.insert(0, str(GROUNDING_DINO_ROOT))

import groundingdino.datasets.transforms as T  # noqa: E402
import torch  # noqa: E402
from groundingdino.models import build_model  # noqa: E402
from groundingdino.util import box_ops  # noqa: E402
from groundingdino.util.slconfig import SLConfig  # noqa: E402
from groundingdino.util.utils import clean_state_dict, get_phrases_from_posmap  # noqa: E402


def crop_center_band(image_pil: Image.Image) -> Image.Image:
    width, height = image_pil.size
    left = int(width * 0.25)
    right = int(width * 0.75)
    result = Image.new(image_pil.mode, (width, height), (0, 0, 0))
    result.paste(image_pil.crop((left, 0, right, height)), (left, 0))
    return result


def load_image(image_path: Path) -> tuple[Image.Image, torch.Tensor]:
    image_pil = crop_center_band(Image.open(image_path).convert("RGB"))
    transform = T.Compose(
        [
            T.RandomResize([800], max_size=1333),
            T.ToTensor(),
            T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )
    image, _ = transform(image_pil, None)
    return image_pil, image


def load_model(config_path: Path, checkpoint_path: Path, device: str):
    args = SLConfig.fromfile(str(config_path))
    args.device = device
    model = build_model(args)
    checkpoint = torch.load(str(checkpoint_path), map_location="cpu")
    model.load_state_dict(clean_state_dict(checkpoint["model"]), strict=False)
    return model.eval().to(device)


def ensure_checkpoint(checkpoint_path: Path, cache_dir: Path | None = None) -> Path:
    if checkpoint_path.is_file():
        return checkpoint_path

    if cache_dir is None:
        cache_dir = Path("/tmp/groundingdino-cache")
    checkpoint_path = cache_dir / checkpoint_path.name
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = checkpoint_path.with_suffix(".pth.tmp")
    print(
        f"[window_dino] Downloading GroundingDINO checkpoint from "
        f"{GROUNDING_DINO_CHECKPOINT_URL}"
    )
    try:
        with urllib.request.urlopen(GROUNDING_DINO_CHECKPOINT_URL) as response:
            with tmp_path.open("wb") as handle:
                handle.write(response.read())
        tmp_path.replace(checkpoint_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    return checkpoint_path


def get_grounding_output(
    model,
    image: torch.Tensor,
    caption: str,
    box_threshold: float,
    text_threshold: float,
    device: str,
):
    caption = caption.lower().strip()
    if not caption.endswith("."):
        caption += "."

    with torch.no_grad():
        outputs = model(image[None].to(device), captions=[caption])

    logits = outputs["pred_logits"].sigmoid()[0].cpu()
    boxes = outputs["pred_boxes"][0].cpu()
    filt_mask = logits.max(dim=1)[0] > box_threshold
    logits_filt = logits[filt_mask]
    boxes_filt = boxes[filt_mask]

    tokenizer = model.tokenizer
    tokenized = tokenizer(caption)
    phrases = []
    for logit in logits_filt:
        phrases.append(get_phrases_from_posmap(logit > text_threshold, tokenized, tokenizer))
    return boxes_filt, phrases


def draw_boxes(image_pil: Image.Image, boxes: torch.Tensor, labels: list[str]) -> Image.Image:
    draw = ImageDraw.Draw(image_pil)
    width, height = image_pil.size
    for box, label in zip(boxes, labels):
        xyxy = box_ops.box_cxcywh_to_xyxy(box.unsqueeze(0))[0]
        xyxy = xyxy * torch.tensor([width, height, width, height])
        x0, y0, x1, y1 = [int(v.item()) for v in xyxy]
        color = (255, 0, 0)
        draw.rectangle([x0, y0, x1, y1], outline=color, width=4)
        font = ImageFont.load_default()
        bbox = draw.textbbox((x0, y0), label, font)
        draw.rectangle(bbox, fill=color)
        draw.text((x0, y0), label, fill="white", font=font)
    return image_pil


def main() -> int:
    args = json.loads(sys.argv[1])
    image_path = Path(args["image_path"])
    output_dir = image_path.parent / "grounding_dino"
    output_dir.mkdir(parents=True, exist_ok=True)

    device = args["device"]
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Requested CUDA for GroundingDINO but no GPU is available.")

    config_path = GROUNDING_DINO_ROOT / "groundingdino/config/GroundingDINO_SwinT_OGC.py"
    vendored_checkpoint = GROUNDING_DINO_ROOT / "weights/groundingdino_swint_ogc.pth"
    checkpoint_cache_dir = output_dir / ".model_cache"
    checkpoint_path = ensure_checkpoint(vendored_checkpoint, checkpoint_cache_dir)
    image_pil, image = load_image(image_path)
    model = load_model(config_path, checkpoint_path, device)
    boxes, phrases = get_grounding_output(
        model,
        image,
        args["prompt"],
        float(args["box_threshold"]),
        float(args["text_threshold"]),
        device,
    )

    image_pil.save(output_dir / "raw_image.jpg")
    draw_boxes(image_pil.copy(), boxes, phrases).save(output_dir / "pred.jpg")
    np.save(output_dir / "bb.npy", boxes.numpy())

    print(f"[window_dino] Device: {device}")
    print(f"[window_dino] Saved boxes: {len(boxes)}")
    print(f"[window_dino] Output: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
