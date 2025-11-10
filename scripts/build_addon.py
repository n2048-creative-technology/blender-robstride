#!/usr/bin/env python3
"""
Build a self-contained Blender add-on zip from this repository.

The zip will contain a single top-level directory named after the add-on
module slug (derived from bl_info name), including only the files required
to run inside Blender (no dev artifacts).

Output: dist/<slug>-<version>.zip

This script uses only the standard library and does not import the add-on,
so it can run in CI without Blender's Python.
"""

from __future__ import annotations

import ast
import io
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, Tuple, Any, Iterable, List
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def parse_bl_info(init_path: Path) -> Dict[str, Any]:
    """Extract bl_info literal from __init__.py without importing bpy.

    Looks for a top-level assignment like: bl_info = { ... }
    and returns the dict via ast.literal_eval.
    """
    src = read_text(init_path)
    # Very small parser: find the first occurrence of 'bl_info = {' and match braces
    m = re.search(r"bl_info\s*=\s*\{", src)
    if not m:
        raise RuntimeError("bl_info dict not found in __init__.py")
    start = m.start()
    # Find matching closing brace for the dict starting at the first '{'
    brace_level = 0
    end = None
    for i, ch in enumerate(src[start:], start=start):
        if ch == '{':
            brace_level += 1
        elif ch == '}':
            brace_level -= 1
            if brace_level == 0:
                end = i + 1
                break
    if end is None:
        raise RuntimeError("Unterminated bl_info dict in __init__.py")
    dict_text = src[m.end() - 1 : end]
    try:
        bl_info = ast.literal_eval(dict_text)
        if not isinstance(bl_info, dict):  # type: ignore[unreachable]
            raise ValueError
        return bl_info
    except Exception as e:
        raise RuntimeError(f"Failed to parse bl_info: {e}") from e


def slugify(name: str) -> str:
    # Lowercase, replace non-alnum with underscores, squeeze repeats
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower())
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def version_to_str(ver: Tuple[int, int, int] | Iterable[int]) -> str:
    try:
        parts = list(int(x) for x in ver)
        return ".".join(str(x) for x in parts)
    except Exception:
        return "0.0.0"


def collect_files(root: Path) -> List[Path]:
    """Whitelist files and directories to include in the add-on."""
    include_files = [
        root / "__init__.py",
        root / "robstride_can.py",
        root / "deps.py",
        root / "README.md",
    ]
    include_dirs = [
        root / "wheels",
        root / "vendor",
    ]

    files: List[Path] = []
    for p in include_files:
        if p.exists():
            files.append(p)
    for d in include_dirs:
        if d.is_dir():
            for sub in d.rglob("*"):
                if sub.is_file():
                    files.append(sub)
    return files


def build_zip(slug: str, version: str, files: List[Path], root: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"{slug}-{version}.zip"
    zip_path = out_dir / zip_name
    # Write zip with paths prefixed by '<slug>/' to satisfy Blender add-on layout
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for src_path in files:
            rel = src_path.relative_to(root)
            arcname = str(Path(slug) / rel)
            zf.write(src_path, arcname)
    return zip_path


def main() -> int:
    init_py = ROOT / "__init__.py"
    if not init_py.exists():
        print("__init__.py not found in repository root", file=sys.stderr)
        return 2
    bl_info = parse_bl_info(init_py)
    name = bl_info.get("name", "addon")
    version = version_to_str(bl_info.get("version", (0, 0, 0)))
    slug = slugify(name)

    files = collect_files(ROOT)
    if not files:
        print("No files collected for packaging", file=sys.stderr)
        return 3

    out_dir = ROOT / "dist"
    zip_path = build_zip(slug, version, files, ROOT, out_dir)
    print(f"Built: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

