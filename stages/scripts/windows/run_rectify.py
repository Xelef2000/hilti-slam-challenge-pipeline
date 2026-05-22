#!/usr/bin/env python3
"""Rectify the equirectangular window mask using py360convert."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

TEAM6_ROOT = Path(os.environ["TEAM6_ROOT"])
PY360_ROOT = TEAM6_ROOT / "py360convert"
sys.path.insert(0, str(PY360_ROOT))

import py360convert  # noqa: E402


def main() -> int:
    args = json.loads(sys.argv[1])
    mask_path = Path(args["mask_path"])
    output_dir = mask_path.parent / "undistorted"
    output_dir.mkdir(parents=True, exist_ok=True)

    mask = np.load(mask_path)
    perspective_img = py360convert.e2p(
        e_img=mask,
        fov_deg=(200, 200),
        u_deg=0,
        v_deg=0,
        out_hw=mask.shape,
        in_rot_deg=0,
        mode="bilinear",
    )

    output_path = output_dir / "mask_undistorted.png"
    Image.fromarray(perspective_img).save(output_path)
    print(f"[window_rectify] Output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
