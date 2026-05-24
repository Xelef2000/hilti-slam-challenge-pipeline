"""Public ROS-bag window-perception stage."""

from __future__ import annotations

from .windows import WindowsStage


class WindowsRosbagStage(WindowsStage):
    @property
    def name(self) -> str:
        return "windows_rosbag"

    @property
    def description(self) -> str:
        return "Run the full window-perception stack on a ROS2 bag"

    @property
    def requires_ros_runtime(self) -> bool:
        return True

    @property
    def input_type(self) -> str:
        return "rosbag"
