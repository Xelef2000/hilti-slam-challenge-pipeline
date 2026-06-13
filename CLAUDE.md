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

# Run SLAM. --input is a run folder containing a 'rosbag/' subdir.
# Output is written to <output>/<stage>/<input_folder_name>/, e.g. ./out/slam/floor_1/
python pipeline.py --stages slam --input data/floor_1 --output ./out
```

## Architecture

### Pipeline Stages

The pipeline is modular with stages defined in `stages/`:

| Stage | Description | Input Topics | Output |
|-------|-------------|--------------|--------|
| `slam` | OpenVINS visual-inertial SLAM | `/cam0/...`, `/cam1/...` | trajectory.txt |

SLAM consumes the original dual fisheye topics (`/cam0/image_raw/compressed`, `/cam1/image_raw/compressed`) and `/imu/data_raw`.

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
- `stages/slam.py`, `stages/slam_runner.py` - SLAM stage and in-container runtime

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

3. Run: `python pipeline.py --stages my_stage --input <run_folder>`

## CLI Reference

```bash
# Basic usage. <run_folder> must contain a 'rosbag/' subdirectory.
python pipeline.py --stages slam --input <run_folder> [--output <dir>]

# SLAM options
--slam-rate 1.0     # Playback rate (<1 for slower processing)
--slam-timeout 600  # Seconds before timeout

# Process multiple run folders (use quotes for glob)
python pipeline.py --stages slam --input "data/floor_*"
```

Output layout: `<output>/<stage>/<input_folder_name>/` (e.g. `out/slam/floor_1/`).

## Container Details

The pipeline builds containers with:
- Base: `ros:jazzy-ros-base-noble` (Ubuntu 24.04)
- Dependencies: Eigen3, Boost, Ceres, OpenCV, TurboJPEG
- Workspace: `/root/ros2_ws/` with challenge tools and OpenVINS

Data is mounted at runtime, not copied into the container.

## Challenge Tools Reference

Scripts from `hilti-trimble-slam-challenge-2026` used by stages:
- `config/hilti_openvins/` - Camera calibration and SLAM config

## Output Format

Trajectories are saved in TUM format:
```
timestamp tx ty tz qx qy qz qw
```
