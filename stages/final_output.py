"""Collect final trajectories, overlays, and evaluation artifacts."""

import json
import shutil
import tempfile
from pathlib import Path

from .base import Stage, StageConfig, stage_output_path


class FinalOutputStage(Stage):
    """Collect the final pipeline outputs into one folder."""

    @property
    def name(self) -> str:
        return "final_output"

    @property
    def description(self) -> str:
        return "Collect realigned trajectories, overlays, and evaluation into one folder"

    @property
    def requires_container(self) -> bool:
        return False

    @property
    def container_profile(self) -> str:
        return "host"

    def run(self, runner, input_dir: Path, config: StageConfig) -> Path:
        stage_root = Path(tempfile.mkdtemp(prefix=f"{self.name}-", dir=runner.runtime_dir))
        output_dir = stage_root / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # (destination, source_stage, source_filename, description)
        artifacts = [
            (
                "trajectories/base_aligned.csv",
                "align", "trajectory_aligned.csv",
                "SLAM poses converted to cam0, placed in map frame",
            ),
            (
                "trajectories/floorplan_aligned.csv",
                "floorplan_align", "trajectory_floor_aligned.csv",
                "Floorplan ray-matching correction applied",
            ),
            (
                "trajectories/window_aligned.csv",
                "window_align", "trajectory_window_aligned.csv",
                "Window detection correction applied",
            ),
            (
                "trajectories/combined_aligned.csv",
                "combined_align", "trajectory_combined_aligned.csv",
                "Weighted fusion of floorplan and window corrections",
            ),
            (
                "overlays/floorplan_overlay.png",
                "floorplan_overlay", "overlay.png",
                "Trajectory rendered on floorplan (floorplan branch)",
            ),
            (
                "overlays/window_overlay.png",
                "window_overlay", "window_overlay.png",
                "Trajectory rendered on floorplan (window branch)",
            ),
            (
                "overlays/combined_overlay.png",
                "combined_overlay", "combined_overlay.png",
                "All trajectory variants overlaid on floorplan",
            ),
            (
                "alignment/window_alignment_transform.json",
                "window_align", "window_alignment_transform.json",
                "2D yaw + translation from window realignment",
            ),
            (
                "alignment/window_alignment_observations.csv",
                "window_align", "window_alignment_observations.csv",
                "Accepted window constraint observations",
            ),
            (
                "alignment/window_alignment_skipped.csv",
                "window_align", "window_alignment_skipped.csv",
                "Rejected window constraint observations",
            ),
            (
                "alignment/combined_alignment.json",
                "combined_align", "combined_alignment.json",
                "Weighted fusion transform (floorplan + window)",
            ),
            (
                "evaluation/summary.json",
                "final_eval", "summary.json",
                "XY / Z error statistics vs ground truth",
            ),
            (
                "evaluation/matched_errors.csv",
                "final_eval", "matched_errors.csv",
                "Per-pose nearest ground-truth match and error",
            ),
        ]

        manifest = {
            "input": config.extra.get("current_input_path", ""),
            "input_name": config.extra.get("current_input_name", ""),
            "artifacts": [],
            "missing": [],
        }
        for relative_target, stage_name, filename, description in artifacts:
            source = stage_output_path(config, stage_name) / filename
            target = output_dir / relative_target
            if source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                manifest["artifacts"].append(
                    {
                        "name": relative_target,
                        "description": description,
                        "source_stage": stage_name,
                        "source": str(source),
                    }
                )
            else:
                manifest["missing"].append(
                    {
                        "name": relative_target,
                        "description": description,
                        "source_stage": stage_name,
                        "source": str(source),
                    }
                )

        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output_dir / f"{self.name}.log").write_text(
            "\n".join(
                [
                    f"Collected artifacts: {len(manifest['artifacts'])}",
                    f"Missing artifacts: {len(manifest['missing'])}",
                    f"Output: {output_dir}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (output_dir / f"{self.name}.status").write_text("0", encoding="utf-8")

        _print_summary(self.name, manifest, config)

        return output_dir


def _print_summary(stage_name: str, manifest: dict, config: "StageConfig") -> None:
    tag = f"[{stage_name}]"
    sep = "=" * 62
    thin = "-" * 62

    # Canonical destination (exists after the pipeline copies the temp output)
    input_name = config.extra.get("current_input_name", "")
    output_root = config.input_root
    canonical = (
        str(Path(output_root) / stage_name / input_name) if output_root and input_name else "(unknown)"
    )

    print(f"{tag} {sep}")
    print(f"{tag} Final output: {canonical}")
    print(f"{tag} {thin}")

    # Group artifacts by their top-level subdirectory for readability
    groups: dict[str, list[dict]] = {}
    for entry in manifest["artifacts"]:
        group = Path(entry["name"]).parts[0] if "/" in entry["name"] else "other"
        groups.setdefault(group, []).append(entry)

    col = 44  # width for the left (filename) column
    for group, entries in groups.items():
        print(f"{tag} {group.capitalize()}")
        for entry in entries:
            name = entry["name"]
            desc = entry["description"]
            print(f"{tag}   {name:<{col - 2}}{desc}")

    print(f"{tag}   {'manifest.json':<{col - 2}}Full artifact index with source paths")
    print(f"{tag} {thin}")

    n_present = len(manifest["artifacts"])
    n_missing = len(manifest["missing"])
    total = n_present + n_missing
    print(f"{tag} {n_present}/{total} artifacts collected", end="")
    if manifest["missing"]:
        missing_stages = sorted({e["source_stage"] for e in manifest["missing"]})
        print(f", {n_missing} missing (stages not run: {', '.join(missing_stages)})", end="")
    print()
    print(f"{tag} {sep}")
