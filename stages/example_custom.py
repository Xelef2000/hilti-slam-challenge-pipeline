"""
Example custom stage - use this as a template for adding new stages.

To add a new stage:
1. Copy this file and rename it (e.g., my_stage.py)
2. Modify the class to implement your processing
3. Register it in stages/__init__.py:

   from .my_stage import MyStage
   registry.register(MyStage())

4. Run with: python pipeline.py --stages my_stage --input <bag>
"""

import dagger
from .base import Stage, StageConfig


class ExampleStage(Stage):
    """
    Example stage that demonstrates how to create custom processing.

    This stage simply copies the input to output with a marker file.
    Replace the run() method with your actual processing logic.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this stage (used in --stages argument)."""
        return "example"

    @property
    def description(self) -> str:
        """Human-readable description shown in --list-stages."""
        return "Example custom stage (template)"

    @property
    def requires_ros_runtime(self) -> bool:
        """Set to True if this stage needs ros2 launch/nodes running."""
        return False

    @property
    def input_type(self) -> str:
        """What this stage expects: 'rosbag', 'euroc', 'directory', 'trajectory'."""
        return "rosbag"

    @property
    def output_type(self) -> str:
        """What this stage produces."""
        return "directory"

    async def run(
        self,
        container: dagger.Container,
        input_dir: dagger.Directory,
        config: StageConfig,
    ) -> dagger.Directory:
        """
        Execute the stage processing.

        Args:
            container: Dagger container with ROS2 workspace built.
            input_dir: Input directory (from previous stage or host).
            config: Stage configuration options.

        Returns:
            Output directory with results.
        """
        # Example: Run a simple command that processes the input
        # Replace this with your actual processing logic

        process_cmd = f"""
{self.get_ros_source_cmd()} && \\
echo "Processing input directory..." && \\
ls -la /input && \\
mkdir -p /output && \\
cp -r /input/* /output/ && \\
echo "example_stage_completed" > /output/stage_marker.txt && \\
echo "Processing complete!"
"""

        result = (
            container
            .with_mounted_directory("/input", input_dir)
            .with_exec(["/bin/bash", "-c", "mkdir -p /output"])
            .with_exec(["/bin/bash", "-c", process_cmd])
        )

        return result.directory("/output")


# Uncomment the following to auto-register when importing this module:
# from . import registry
# registry.register(ExampleStage())
