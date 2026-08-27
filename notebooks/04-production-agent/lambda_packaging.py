"""Build deployment zips for the Module 4 retrieval Lambdas.

Packaging these functions solves three problems that the notebook cell
that calls `build_lambda_zips` does not need to show:

1. **Platform-targeted wheels.** Lambda runs on Amazon Linux, so the
   third-party install must target that platform's wheels even when this
   notebook runs on a different one.
2. **Shared-package source.** The `workshop` package is a local source
   tree in this repository rather than a distribution on an index, so
   the zip cannot simply pip-install it by name. Its pure-Python source
   and JSON fixtures are copied in directly instead, and only those:
   `copy_shared_package` names what it wants rather than naming what to
   skip. `notebooks/workshop/` is also a working directory. A local
   `uv sync` leaves a 356 MB `.venv/` there, an editable install leaves
   `build/` and `workshop.egg-info/`, and a denylist has to be extended
   for each one before the next tool invents a directory that silently
   blows past Lambda's 50 MB zipped and 250 MB unzipped limits. An
   allowlist fails the other way: a new module the Lambda genuinely
   needs has to match `*.py` or be added to `SHARED_DATA_DIRS`, and that
   failure is a missing import at build time rather than a rejected
   upload after a long install.
3. **Excluded transitive weight.** `neo4j-graphrag` pulls in `numpy` and
   `scipy` for an experimental extraction pipeline and a sentence
   embedder that this retrieval path never imports. Leaving them out
   keeps each zip within Lambda's direct-upload limit.

Both Lambda functions share every dependency and differ only in their
entry point, so the platform-targeted install runs once per call to
`build_lambda_zips` and is reused for every entry point passed in.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


# The only subdirectory of `notebooks/workshop/` that ships. It holds the JSON
# fixtures the retrieval path reads, so leaving it out breaks the Lambda rather
# than shrinking it.
SHARED_DATA_DIRS: tuple[str, ...] = ("fixtures",)


def copy_shared_package(shared_package: Path, package_dir: Path) -> None:
    """Copy the shared package's Python modules and JSON fixtures into the bundle.

    An allowlist, for the reason given in the module docstring: the source
    directory doubles as a local working directory, and anything it grows that
    is not a top-level module or a named data directory stays out of the zip.
    """
    target = package_dir / "workshop"
    target.mkdir(parents=True)
    for module in sorted(shared_package.glob("*.py")):
        shutil.copy2(module, target / module.name)
    for name in SHARED_DATA_DIRS:
        source = shared_package / name
        if source.is_dir():
            shutil.copytree(
                source,
                target / name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )


def install_dependencies(
    package_dir: Path,
    requirements_path: Path,
    arch: str,
    python_version: str,
) -> None:
    """Install the Lambda's third-party wheels for the Lambda's platform."""
    platform_tag = (
        "manylinux2014_aarch64" if arch == "arm64" else "manylinux2014_x86_64"
    )
    abi = "cp" + python_version.replace(".", "")
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "--platform", platform_tag,
            "--python-version", python_version,
            "--implementation", "cp",
            "--abi", abi,
            "--only-binary", ":all:",
            "--ignore-installed",
            "--target", str(package_dir),
            "--requirement", str(requirements_path),
        ],
        check=True,
    )


def zip_package(
    package_dir: Path,
    entry_point: Path,
    excluded_prefixes: tuple[str, ...],
) -> bytes:
    """Zip the shared package directory plus one handler's entry point."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package_dir.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(package_dir)
            if relative.parts[0].startswith(excluded_prefixes):
                continue
            archive.write(path, relative.as_posix())
        # The entry point goes at the zip root, where the runtime looks for it.
        archive.writestr("lambda_function.py", entry_point.read_text())
    return buffer.getvalue()


def build_lambda_zips(
    entry_points: dict[str, Path],
    shared_package: Path,
    requirements_path: Path,
    arch: str = "arm64",
    python_version: str = "3.12",
    excluded_prefixes: tuple[str, ...] = ("numpy", "scipy"),
) -> dict[str, bytes]:
    """Build one deployment package per entry point over one shared install.

    `entry_points` maps a deployable name to its `lambda_function.py` path.
    """
    build_dir = Path(tempfile.mkdtemp(prefix="hotel-lambda-"))
    try:
        package_dir = build_dir / "package"
        package_dir.mkdir(parents=True)
        print("Installing Lambda dependencies (Linux wheels)...")
        install_dependencies(package_dir, requirements_path, arch, python_version)
        copy_shared_package(shared_package, package_dir)
        return {
            name: zip_package(package_dir, entry_point, excluded_prefixes)
            for name, entry_point in entry_points.items()
        }
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)
