# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python-orchestrated container pipeline for the Hilti-Trimble SLAM Challenge 2026. Processes ROS2 bags containing dual fisheye camera images and IMU data from construction sites to estimate camera trajectories.

**Key Technologies**: Python 3.10+, Docker/Apptainer/Singularity, ROS 2 Jazzy (containerized), OpenVINS

## Quick Start

```bash
# Optional but recommended
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# List available stages
python pipeline.py --list-stages

# Run stitching on a bag
python pipeline.py --stages stitch --input data/floor_1/2025-05-05/run_1/rosbag

# Run SLAM (uses original dual fisheye cameras)
python pipeline.py --stages slam --input data/floor_1/2025-05-05/run_1/rosbag --output results/
```

## Architecture

### Pipeline Stages

The pipeline is modular with stages defined in `stages/`:

| Stage | Description | Input Topics | Output |
|-------|-------------|--------------|--------|
| `stitch` | Dual fisheye to 360° equirectangular | `/cam0/...`, `/cam1/...` | rosbag with `/pano/...` |
| `convert` | ROS2 bag to EuRoC format | `/cam0/...`, `/cam1/...` | euroc directory |
| `slam` | OpenVINS visual-inertial SLAM | `/cam0/...`, `/cam1/...` | trajectory.txt |

**Important**: `stitch` and `slam` are independent stages. SLAM requires the original dual fisheye topics (`/cam0/image_raw/compressed`, `/cam1/image_raw/compressed`), NOT the stitched panorama.

### Data Flow
```
Host: rosbag files (mounted, not copied into container)
    ↓
Container: ros:jazzy-ros-base-noble + challenge tools + OpenVINS
    ↓
Selected stage processes data
    ↓
Host: Results exported to --output directory
```

### Key Files
- `pipeline.py` - Main orchestrator with CLI
- `stages/base.py` - Stage base class and registry
- `stages/stitch.py`, `convert.py`, `slam.py` - Built-in stages
- `stages/example_custom.py` - Template for custom stages

### Adding Custom Stages

1. Create `stages/my_stage.py`:
```python
from pathlib import Path

from runtime_backend import ExecutionSpec

from .base import Stage, StageConfig

class MyStage(Stage):
    @property
    def name(self) -> str:
        return "my_stage"

    @property
    def description(self) -> str:
        return "My custom processing"

    def run(self, runner, input_dir: Path, config: StageConfig) -> Path:
        wrapper = \"\"\"#!/bin/bash
set +e
mkdir -p /output
cp -a /input/. /output/
echo "example" > /output/stage_marker.txt
echo "0" > /output/my_stage.status
\"\"\"
        return runner.run_stage(
            container_profile=self.container_profile,
            input_dir=input_dir,
            config=config,
            spec=ExecutionSpec(
                stage_name=self.name,
                command=["/bin/bash", "/stage_runtime/my_stage.sh"],
                files={"my_stage.sh": wrapper},
            ),
        )
```

2. Register in `stages/__init__.py`:
```python
from .my_stage import MyStage
registry.register(MyStage())
```

3. Run: `python pipeline.py --stages my_stage --input <bag>`

## CLI Reference

```bash
# Basic usage
python pipeline.py --stages <stage1> [stage2 ...] --input <path> [--output <dir>]

# Stitching options
--no-torch          # Use OpenCV instead of PyTorch
--device auto|cpu|cuda
--jpeg-quality 95   # 1-100

# SLAM options
--slam-rate 1.0     # Playback rate (<1 for slower processing)
--slam-timeout 600  # Seconds before timeout

# Process multiple bags (use quotes for glob)
python pipeline.py --stages slam --input "data/floor_*/*/rosbag"
```

## Container Details

The pipeline builds containers with:
- Base: `ros:jazzy-ros-base-noble` (Ubuntu 24.04)
- Dependencies: Eigen3, Boost, Ceres, OpenCV, TurboJPEG
- Workspace: `/root/ros2_ws/` with challenge tools and OpenVINS

Data is mounted at runtime, not copied into the container.

## Challenge Tools Reference

Scripts from `hilti-trimble-slam-challenge-2026` used by stages:
- `bag_helper/image_stitching.py` - Fisheye stitching (EUCM/Pinhole models)
- `bag_helper/ros2bag_to_euroc.py` - Format conversion
- `config/hilti_openvins/` - Camera calibration and SLAM config

## Output Format

Trajectories are saved in TUM format:
```
timestamp tx ty tz qx qy qz qw
```
