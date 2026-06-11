# Repository Guidelines

## Project Structure & Module Organization
- `pipeline.py` is the CLI entrypoint and Python container-runtime orchestrator.
- `stages/` contains the `slam` stage (`slam.py`, `slam_runner.py`) plus `base.py` and registry wiring in `__init__.py`.
- `data/` holds example ROS2 bag inputs (mounted into containers; not copied).
- `results/` is the default output area for exported artifacts.

## Build, Test, and Development Commands
- `pip install -r requirements.txt` installs runtime dependencies.
- `pip install -e ".[dev]"` installs dev tools (pytest, ruff).
- `python pipeline.py --list-stages` lists available stages.
- `python pipeline.py --stages slam --input data/floor_1 --output ./out` runs SLAM. `--input` is a run folder containing a `rosbag/` subdir; output lands in `./out/slam/floor_1/`.

## Coding Style & Naming Conventions
- Python 3.10+ with 4-space indentation.
- Linting uses Ruff with line length 100 (`ruff check .`).
- Stage files use snake_case; stage classes use CamelCase and implement a `name` property with a matching snake_case identifier.

## Testing Guidelines
- Pytest is the preferred framework (`pytest`).
- No tests are present yet; add new tests under `tests/` and name files `test_*.py`.

## Commit & Pull Request Guidelines
- No Git history is available in this workspace, so no established commit convention can be inferred.
- Use short, imperative commit subjects (e.g., "Add SLAM stage option flags").
- PRs should include a brief description, the stages/commands exercised, and sample output paths when relevant.

## Data & Configuration Notes
- Inputs are ROS2 bags under `data/<site>/<date>/run_<n>/rosbag`.
- Containers are built from the repo Dockerfiles and run via Docker or Apptainer/Singularity; data is mounted at runtime, so avoid writing into `data/` during processing.
