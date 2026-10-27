"""Resolve resources from the installed skill, independent of process cwd."""
from pathlib import Path


def skill_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resource_path(relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("resource path must be relative and cannot traverse parents")
    return skill_root() / path
