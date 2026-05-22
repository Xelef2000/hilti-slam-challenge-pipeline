Vendored runtime files for the standalone window-segmentation stages.

Contents:
- `GroundingDINO/`: trimmed source tree plus `groundingdino_swint_ogc.pth`
- `sam3/`: trimmed source tree needed by `build_sam3_image_model`
- `py360convert/`: importable package used for mask rectification

Deliberately excluded:
- local virtual environments
- notebooks, demos, generated outputs
- test data and unrelated assets
