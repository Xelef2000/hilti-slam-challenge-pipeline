"""SLAM stage - runs OpenVINS visual-inertial odometry."""

from pathlib import Path

import dagger

from .base import Stage, StageConfig


class SlamStage(Stage):
    """Run OpenVINS visual-inertial SLAM."""

    @property
    def name(self) -> str:
        return "slam"

    @property
    def description(self) -> str:
        return "Run OpenVINS visual-inertial SLAM"

    @property
    def requires_ros_runtime(self) -> bool:
        return True

    @property
    def input_type(self) -> str:
        return "rosbag"

    @property
    def output_type(self) -> str:
        return "trajectory"

    async def run(
        self,
        container: dagger.Container,
        input_dir: dagger.Directory,
        config: StageConfig,
    ) -> dagger.Directory:
        """Run OpenVINS SLAM on the input bag."""

        # Read the runner script
        runner_path = Path(__file__).parent / "slam_runner.py"
        runner_script = runner_path.read_text()

        # Create wrapper that handles output capture
        wrapper = f"""#!/bin/bash
set +e
mkdir -p /output

# Preserve floorplan assets (if present) for downstream overlay stage.
for candidate in /input/floorplan.* /input/map.*; do
  if [ -f "$candidate" ]; then
    cp "$candidate" /output/
  fi
done

python3 /tmp/slam_runner.py {config.slam_rate} {config.slam_timeout} 2>&1 | tee /output/slam.log
STATUS=${{PIPESTATUS[0]}}
echo "$STATUS" > /output/slam.status
exit 0
"""

        result = (
            container
            .with_mounted_directory("/input", input_dir)
            .with_exec(["/bin/bash", "-c", "mkdir -p /output"])
            .with_new_file("/tmp/slam_runner.py", contents=runner_script, permissions=0o755)
            .with_new_file("/tmp/run_slam.sh", contents=wrapper, permissions=0o755)
            .with_exec(["/bin/bash", "/tmp/run_slam.sh"])
        )

        return result.directory("/output")
