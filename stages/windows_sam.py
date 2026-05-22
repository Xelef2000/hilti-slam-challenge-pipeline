"""SAM3-based window segmentation stage."""

import json

import dagger

from .base import Stage, StageConfig


class WindowsSamStage(Stage):
    @property
    def name(self) -> str:
        return "window_sam"

    @property
    def description(self) -> str:
        return "Segment windows from GroundingDINO boxes with SAM3"

    @property
    def container_profile(self) -> str:
        return "windows"

    @property
    def input_type(self) -> str:
        return "directory"

    @property
    def output_type(self) -> str:
        return "directory"

    async def run(
        self,
        container: dagger.Container,
        input_dir: dagger.Directory,
        config: StageConfig,
    ) -> dagger.Directory:
        image_name = str(config.extra["current_input_name"])
        runtime_args = json.dumps(
            {
                "image_path": f"/output/{image_name}",
                "boxes_path": "/output/grounding_dino/bb.npy",
                "device": config.windows_device,
            }
        )

        stage_cmd = f"""#!/bin/bash
set -euo pipefail
mkdir -p /output
cp -a /input/. /output/
export TEAM6_ROOT=/opt/team6
export PYTHONPATH=/opt/team6/GroundingDINO:/opt/team6/sam3:/opt/team6/py360convert:$PYTHONPATH
python /opt/pipeline_scripts/windows/run_sam3.py '{runtime_args}'
"""

        wrapper_cmd = f"""#!/bin/bash
set +e
/bin/bash /tmp/{self.name}.sh 2>&1 | tee /output/{self.name}.log
STATUS=${{PIPESTATUS[0]}}
echo "$STATUS" > /output/{self.name}.status
exit 0
"""

        result = (
            container
            .with_mounted_directory("/input", input_dir)
            .with_exec(["/bin/bash", "-c", "mkdir -p /output"])
            .with_new_file(f"/tmp/{self.name}.sh", contents=stage_cmd, permissions=0o755)
            .with_new_file(
                f"/tmp/{self.name}_wrapper.sh",
                contents=wrapper_cmd,
                permissions=0o755,
            )
            .with_exec(["/bin/bash", f"/tmp/{self.name}_wrapper.sh"])
        )
        return result.directory("/output")
