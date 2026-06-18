"""Convert a SLAM trajectory to cam0 CSV, optionally aligned to the map frame.

Runs on the host (pure numpy). Reads:
  - <previous stage output>/trajectory.txt   (TUM format: `timestamp tx ty tz qx qy qz qw`)
  - <original input folder>/orientation.json when --align-start-position is enabled
    (JSON produced by save_tf.py: contains `T_parent_child` (4x4 T_map_global) and `yaw_rad`)

The SLAM trajectory from `/ov_msckf/poseimu` is the **IMU** body pose in OpenVINS
world (`global` frame). This stage always converts it to a **cam0** pose CSV. If start
alignment is disabled, that cam0 pose remains in OpenVINS world. If start alignment is
enabled, `orientation.json` supplies `T_map_global` directly as a static ROS TF,
which is used to transform all cam0 poses into the map frame.

Both `global` (OpenVINS world) and `map` are gravity-aligned, so T_map_global is a
pure yaw rotation plus a 3D translation with no residual pitch/roll tilt.
"""

import csv
import json
import math
import tempfile
from pathlib import Path

import numpy as np

from ._geometry import T_IMU_CAM, matrix_to_pose, pose_to_matrix
from .base import Stage, StageConfig

TRAJECTORY_FILENAME = "trajectory.txt"
INITIAL_POSE_FILENAME = "orientation.json"
OUTPUT_CSV = "trajectory_aligned.csv"


class AlignStage(Stage):
    """Convert SLAM poses to cam0 CSV, optionally aligned to a known initial pose."""

    @property
    def name(self) -> str:
        return "align"

    @property
    def description(self) -> str:
        return "Convert SLAM trajectory to cam0 CSV, optionally start-aligned"

    @property
    def requires_container(self) -> bool:
        return False

    @property
    def container_profile(self) -> str:
        return "host"

    def run(self, runner, input_dir: Path, config: StageConfig) -> Path:
        trajectory_path = input_dir / TRAJECTORY_FILENAME
        if not trajectory_path.is_file():
            raise FileNotFoundError(
                f"Expected '{TRAJECTORY_FILENAME}' in previous stage output: {input_dir}"
            )

        slam_poses = _load_pose_table(trajectory_path)
        T_out_ovworld = np.eye(4)
        log_lines = [
            f"Trajectory: {trajectory_path} ({len(slam_poses)} poses)",
        ]

        if config.align_start_position:
            initial_pose_path = input_dir / INITIAL_POSE_FILENAME
            if not initial_pose_path.is_file():
                raise FileNotFoundError(
                    f"Expected '{INITIAL_POSE_FILENAME}' in stage input: {input_dir}. "
                    "Run the save_tf stage before align."
                )

            T_out_ovworld, yaw_rad = _load_orientation_json(initial_pose_path)
            log_lines.extend(
                [
                    "Start alignment: enabled",
                    f"Orientation: {initial_pose_path}",
                    f"Yaw (global -> map): {math.degrees(yaw_rad):+.3f} deg",
                ]
            )
        else:
            log_lines.append(
                "Start alignment: disabled; output cam0 poses remain in OpenVINS world"
            )

        aligned = _apply_to_imu_get_cam(slam_poses[:, 1:], T_out_ovworld)

        stage_root = Path(
            tempfile.mkdtemp(prefix=f"{self.name}-", dir=runner.runtime_dir)
        )
        output_dir = stage_root / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        _write_csv(output_dir / OUTPUT_CSV, slam_poses[:, 0], aligned)

        log_lines.append(f"Trajectory CSV written: {output_dir / OUTPUT_CSV}")
        (output_dir / f"{self.name}.log").write_text(
            "\n".join(log_lines) + "\n", encoding="utf-8"
        )
        (output_dir / f"{self.name}.status").write_text("0", encoding="utf-8")
        for line in log_lines:
            print(f"[{self.name}] {line}")

        return output_dir


def _load_pose_table(path: Path) -> np.ndarray:
    """Load whitespace- or comma-separated rows of `timestamp tx ty tz qx qy qz qw`."""
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.replace(",", " ").split()
            if len(parts) != 8:
                continue
            rows.append([float(p) for p in parts])
    if not rows:
        raise ValueError(f"No pose rows found in {path}")
    return np.asarray(rows, dtype=float)


def _load_orientation_json(path: Path):
    """Load T_map_global from orientation.json produced by save_tf.py.

    Returns (T_map_global, yaw_rad) where T_map_global is a 4x4 SE(3) matrix.
    """
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    T = np.array(data["T_parent_child"], dtype=float)
    yaw_rad = float(data["yaw_rad"])
    return T, yaw_rad


def _apply_to_imu_get_cam(slam_imu_poses: np.ndarray, T_map_ovworld: np.ndarray) -> np.ndarray:
    """Map each SLAM IMU pose to the corresponding cam0 pose in map frame (eq. 1)."""
    out = np.empty_like(slam_imu_poses)
    for i in range(slam_imu_poses.shape[0]):
        M_slam_i = pose_to_matrix(slam_imu_poses[i])
        T_map_cam_i = T_map_ovworld @ M_slam_i @ T_IMU_CAM
        out[i] = matrix_to_pose(T_map_cam_i)
    return out


def _write_csv(path: Path, timestamps: np.ndarray, poses: np.ndarray) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["# timestamp", "tx", "ty", "tz", "qx", "qy", "qz", "qw"])
        for t, p in zip(timestamps, poses):
            writer.writerow(
                [
                    f"{t:.9f}",
                    f"{p[0]:.9f}",
                    f"{p[1]:.9f}",
                    f"{p[2]:.9f}",
                    f"{p[3]:.9f}",
                    f"{p[4]:.9f}",
                    f"{p[5]:.9f}",
                    f"{p[6]:.9f}",
                ]
            )
