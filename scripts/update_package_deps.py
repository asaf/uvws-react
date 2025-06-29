#!/usr/bin/env python
import argparse
import re
import subprocess
from pathlib import Path
from typing import Any

import tomllib

# ---------------------
# CLI Argument Parsing
# ---------------------
parser = argparse.ArgumentParser(description="Update workspace dependency versions.")
parser.add_argument("package_name", help="Name of the package to update")
parser.add_argument(
    "--prefix", default="", help="Prefix to strip from package name (optional)"
)
args = parser.parse_args()

PACKAGE_NAME = args.package_name
PACKAGE_PREFIX = args.prefix

# ---------------------
# Path Setup
# ---------------------
ROOT_DIR = Path(__file__).parent.parent

if PACKAGE_NAME == "root":
    PACKAGE_DIR = ROOT_DIR
    PACKAGE_PYPROJECT = ROOT_DIR / "pyproject.toml"
else:
    # Strip the prefix if provided
    package_dir_name = PACKAGE_NAME.removeprefix(PACKAGE_PREFIX)
    PACKAGE_DIR = ROOT_DIR / "packages" / package_dir_name
    PACKAGE_PYPROJECT = PACKAGE_DIR / "pyproject.toml"


# ---------------------
# Functions
# ---------------------
def get_workspace_dependencies() -> Any:
    """Extract dependencies from `[tool.uv.sources]` in the package's `pyproject.toml`."""
    with open(PACKAGE_PYPROJECT, "rb") as f:
        pyproject = tomllib.load(f)
    sources = pyproject.get("tool", {}).get("uv", {}).get("sources", {})
    return {
        key: value for key, value in sources.items() if value == {"workspace": True}
    }


def get_package_version(package_name: str) -> Any:
    """Read the package version from the appropriate `pyproject.toml`."""
    if package_name == "root":
        package_pyproject = ROOT_DIR / "pyproject.toml"
    else:
        package_dir_name = package_name.removeprefix(PACKAGE_PREFIX)
        package_pyproject = ROOT_DIR / "packages" / package_dir_name / "pyproject.toml"

    if not package_pyproject.exists():
        raise FileNotFoundError(f"Missing pyproject.toml for {package_name}")

    with open(package_pyproject, "rb") as f:
        pyproject = tomllib.load(f)

    return pyproject["project"]["version"]


def update_dependencies() -> bool:
    """Update only the `dependencies` field in `pyproject.toml` while preserving formatting."""
    with open(PACKAGE_PYPROJECT, "r", encoding="utf-8") as f:
        pyproject_text = f.read()

    dependencies_match = re.search(
        r"dependencies\s*=\s*\[(.*?)\]", pyproject_text, re.DOTALL
    )
    if not dependencies_match:
        print("No dependencies found in pyproject.toml.")
        return False

    dependencies_text = dependencies_match.group(1).strip()
    dependencies = [
        d.strip().strip('"').strip("'")
        for d in dependencies_text.split(",")
        if d.strip()
    ]

    workspace_deps = get_workspace_dependencies()
    updated_deps = []
    updated = False

    for dep in dependencies:
        dep_name = dep.split("==")[0]
        if dep_name in workspace_deps:
            new_version = get_package_version(dep_name)
            current_version = dep.split("==")[1] if "==" in dep else None
            if current_version != new_version:
                print(f"Updating {dep_name} from {current_version} to {new_version}")
                updated_deps.append(f'"{dep_name}=={new_version}"')
                updated = True
            else:
                updated_deps.append(f'"{dep}"')
        else:
            updated_deps.append(f'"{dep}"')

    if updated:
        new_dependencies_text = ",\n    ".join(updated_deps)
        new_pyproject_text = re.sub(
            r"dependencies\s*=\s*\[(.*?)\]",
            f"dependencies = [\n    {new_dependencies_text}\n]",
            pyproject_text,
            flags=re.DOTALL,
        )

        with open(PACKAGE_PYPROJECT, "w", encoding="utf-8") as f:
            f.write(new_pyproject_text)

        print("Updated dependencies:", updated_deps)
        return True
    else:
        print("No dependency updates needed.")
        return False


def git_commit_and_push() -> None:
    """Commit and push changes to GitHub"""
    subprocess.run(
        ["git", "config", "--global", "user.name", "github-actions"], check=True
    )
    subprocess.run(
        ["git", "config", "--global", "user.email", "actions@users.noreply.github.com"],
        check=True,
    )
    subprocess.run(["git", "add", str(PACKAGE_PYPROJECT)], check=True)
    subprocess.run(
        [
            "git",
            "commit",
            "-m",
            f"chore({PACKAGE_NAME}): update workspace dependencies [skip ci]",
        ],
        check=True,
    )
    subprocess.run(["git", "push"], check=True)
    print("Committed and pushed updated dependencies.")


# ---------------------
# Main Execution
# ---------------------
if __name__ == "__main__":
    updated = update_dependencies()
    if updated:
        git_commit_and_push()
