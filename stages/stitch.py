"""Image stitching stage - converts dual fisheye to 360 equirectangular."""

import dagger
from .base import Stage, StageConfig


class StitchStage(Stage):
    """Convert dual fisheye images to 360° equirectangular panorama."""

    @property
    def name(self) -> str:
        return "stitch"

    @property
    def description(self) -> str:
        return "Convert dual fisheye images to 360° equirectangular panorama"

    @property
    def input_type(self) -> str:
        return "rosbag"

    @property
    def output_type(self) -> str:
        return "rosbag"

    async def run(
        self,
        container: dagger.Container,
        input_dir: dagger.Directory,
        config: StageConfig,
    ) -> dagger.Directory:
        """Run image stitching on the input bag."""

        # Prepare torch args; verify availability inside the container at runtime.
        torch_args = ""
        if config.use_torch:
            torch_args = f"--use-torch --device {config.torch_device}"

        # The stitching script path in the container
        script_path = (
            "/root/ros2_ws/src/hilti-trimble-slam-challenge-2026"
            "/challenge_tools_ros/bag_helper/image_stitching.py"
        )
        config_base = (
            "/root/ros2_ws/src/hilti-trimble-slam-challenge-2026"
            "/config/hilti_openvins"
        )

        stitch_cmd = f"""#!/bin/bash
set -euxo pipefail

set +u
source /opt/ros/jazzy/setup.bash
source /root/ros2_ws/install/setup.bash
set -u

echo "[stitch] Python: $(python3 --version)"
echo "[stitch] ros2 path: $(command -v ros2 || true)"
echo "[stitch] colcon path: $(command -v colcon || true)"
echo "[stitch] git path: $(command -v git || true)"
echo "[stitch] Input bag contents:"
ls -la /input
echo "[stitch] Script path: {script_path}"
test -f {script_path}
echo "[stitch] Config path: {config_base}/kalibr_imucam_chain.yaml"
test -f {config_base}/kalibr_imucam_chain.yaml
test -f {config_base}/mask_cam0.png
test -f {config_base}/mask_cam1.png
echo "[stitch] Running stitching script..."
rm -rf /output/rosbag_pano

TORCH_ARGS=""
if {str(config.use_torch).lower()}; then
  if python3 - <<'PY'
import importlib.util
import sys
sys.exit(0 if importlib.util.find_spec("torch") else 1)
PY
  then
    TORCH_ARGS="{torch_args}"
  else
    echo "[stitch] PyTorch not available; falling back to OpenCV stitching"
  fi
fi

{{
python3 {script_path} \
    --bag /input \
    --yaml {config_base}/kalibr_imucam_chain.yaml \
    --mask0 {config_base}/mask_cam0.png \
    --mask1 {config_base}/mask_cam1.png \
    --out /output/rosbag_pano \
    --jpeg-quality {config.jpeg_quality} \
    $TORCH_ARGS
}}

touch /output/rosbag_pano/.stitched
echo "[stitch] Output bag contents:"
ls -la /output/rosbag_pano
"""

        wrapper_script = """#!/bin/bash
set +e
mkdir -p /output
/bin/bash /tmp/run_stitch.sh 2>&1 | tee /output/stitch.log
STATUS=${PIPESTATUS[0]}
echo "$STATUS" > /output/stitch.status
if [ $STATUS -ne 0 ]; then
  echo "[stitch] Wrapper detected failure, preserving logs" | tee -a /output/stitch.log
fi
exit 0
"""

        result = (
            container
            .with_mounted_directory("/input", input_dir)
            .with_exec(["/bin/bash", "-c", "mkdir -p /output"])
            .with_new_file("/tmp/run_stitch.sh", contents=stitch_cmd, permissions=0o755)
            .with_new_file("/tmp/run_stitch_wrapper.sh", contents=wrapper_script, permissions=0o755)
            .with_exec(["/bin/bash", "/tmp/run_stitch_wrapper.sh"])
        )

        return result.directory("/output")
