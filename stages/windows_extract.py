"""Extract a representative image from a ROS2 bag for window inference."""

from __future__ import annotations

import json
from pathlib import Path

from runtime_backend import ExecutionSpec

from .base import Stage, StageConfig


class WindowsExtractStage(Stage):
    @property
    def name(self) -> str:
        return "windows_extract"

    @property
    def description(self) -> str:
        return "Extract one camera frame from a ROS2 bag for window inference"

    @property
    def requires_ros_runtime(self) -> bool:
        return True

    @property
    def input_type(self) -> str:
        return "rosbag"

    @property
    def output_type(self) -> str:
        return "directory"

    def run(
        self,
        runner,
        input_dir: Path,
        config: StageConfig,
    ) -> Path:
        output_image_name = "input.png"
        config.extra["current_input_name"] = output_image_name

        preferred_topics = [
            config.windows_topic,
            "/cam0/image_raw/compressed",
            "/cam1/image_raw/compressed",
            "/cam0/image_raw",
            "/cam1/image_raw",
        ]
        runtime_args = json.dumps(
            {
                "bag_path": "/input",
                "output_image_path": f"/output/{output_image_name}",
                "source_metadata_path": "/output/windows_source.json",
                "frame_index": config.windows_frame_index,
                "preferred_topics": preferred_topics,
            }
        )

        ros_setup = self.get_ros_source_cmd()
        stage_cmd = f"""#!/bin/bash
set -euo pipefail
mkdir -p /output
export WINDOWS_PIPELINE_ROOT=/opt/windows_pipeline
{ros_setup}
python3 /opt/pipeline_scripts/windows/extract_ros_frame.py '{runtime_args}'
"""

        wrapper_cmd = f"""#!/bin/bash
set +e
/bin/bash /stage_runtime/{self.name}.sh 2>&1 | tee /output/{self.name}.log
STATUS=${{PIPESTATUS[0]}}
echo "$STATUS" > /output/{self.name}.status
exit 0
"""

        return runner.run_stage(
            container_profile=self.container_profile,
            input_dir=input_dir,
            config=config,
            spec=ExecutionSpec(
                stage_name=self.name,
                command=["/bin/bash", f"/stage_runtime/{self.name}_wrapper.sh"],
                files={
                    f"{self.name}.sh": stage_cmd,
                    f"{self.name}_wrapper.sh": wrapper_cmd,
                },
            ),
        )
