"""Clean stage - removes pipeline outputs on the host."""

import dagger

from .base import Stage, StageConfig


class CleanStage(Stage):
    """Remove pipeline-generated outputs for a run."""

    @property
    def name(self) -> str:
        return "clean"

    @property
    def description(self) -> str:
        return "Remove pipeline outputs (leaves input data intact)"

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
        """No-op in container; host cleanup is handled in pipeline."""
        return input_dir
