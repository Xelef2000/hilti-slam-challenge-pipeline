"""Format conversion stage - converts ROS2 bags to EuRoC format."""

import dagger
from .base import Stage, StageConfig


class ConvertStage(Stage):
    """Convert ROS2 bag to EuRoC dataset format."""

    @property
    def name(self) -> str:
        return "convert"

    @property
    def description(self) -> str:
        return "Convert ROS2 bag to EuRoC dataset format"

    @property
    def input_type(self) -> str:
        return "rosbag"

    @property
    def output_type(self) -> str:
        return "euroc"

    async def run(
        self,
        container: dagger.Container,
        input_dir: dagger.Directory,
        config: StageConfig,
    ) -> dagger.Directory:
        """Convert ROS2 bag to EuRoC format."""

        script_path = (
            "/root/ros2_ws/src/hilti-trimble-slam-challenge-2026"
            "/challenge_tools_ros/bag_helper/ros2bag_to_euroc.py"
        )

        # Get custom topic names from config if provided
        cam_topics = config.extra.get(
            "cam_topics",
            "/cam0/image_raw/compressed /cam1/image_raw/compressed"
        )
        imu_topic = config.extra.get("imu_topic", "/imu/data")

        convert_cmd = f"""
{self.get_ros_source_cmd()} && \\
python3 {script_path} \\
    --bag /input \\
    --out /output \\
    --cam-topics {cam_topics} \\
    --imu-topic {imu_topic}
"""

        result = (
            container
            .with_mounted_directory("/input", input_dir)
            .with_exec(["/bin/bash", "-c", "mkdir -p /output"])
            .with_exec(["/bin/bash", "-c", convert_cmd])
        )

        return result.directory("/output")
