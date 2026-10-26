"""Set up a pinned, reusable Brickwright runtime without changing a user's project."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPOSITORY = "https://github.com/kimjanise/brickwright.git"
# Tested build authoring, bundled meshes, and live Pick a Brick pricing.
REVISION = "19d32dd526c471452c43d799bb399356bc4ba0ef"


def run(args: list[str], cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True, stdout=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        help="Reuse an existing compatible checkout without modifying it",
    )
    args = parser.parse_args()
    if args.repo:
        repo = args.repo.expanduser().resolve()
    else:
        if not shutil.which("git") or not shutil.which("uv"):
            raise SystemExit("Install git and uv first, then rerun this script.")
        cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        repo = cache / "lego-build" / f"brickwright-{REVISION[:12]}"
        if not repo.exists():
            repo.parent.mkdir(parents=True, exist_ok=True)
            run(
                [
                    "git",
                    "clone",
                    "--filter=blob:none",
                    "--no-checkout",
                    REPOSITORY,
                    str(repo),
                ]
            )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        if head.stdout.strip() != REVISION or not (repo / "pyproject.toml").is_file():
            run(["git", "checkout", "--detach", REVISION], repo)
        run(["uv", "sync", "--frozen", "--all-packages", "--group", "dev"], repo)
    binaries = repo / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    python = binaries / ("python.exe" if os.name == "nt" else "python")
    cli = binaries / ("brickwright.exe" if os.name == "nt" else "brickwright")
    if not python.is_file() or not cli.is_file():
        raise SystemExit(
            "Runtime missing. Run uv sync --all-packages --group dev in the checkout."
        )
    if not args.repo:
        run(["uv", "pip", "install", "--python", str(python), "reportlab==5.1.0"])
    run(
        [
            str(python),
            "-c",
            "from brickwright.pricing import PickABrickClient; from brickwright.record import Record; import numpy; import PIL; import reportlab",
        ]
    )
    print(
        json.dumps(
            {"repository": str(repo), "python": str(python), "brickwright": str(cli)},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
