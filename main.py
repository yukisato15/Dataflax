#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Compatibility launcher for the reorganized Dataflux workspace."""

from pathlib import Path
import runpy
import sys


def main() -> int:
    project_main = Path(__file__).resolve().parent / "Dataflux" / "main.py"
    if not project_main.exists():
        print(f"Error: launcher target not found: {project_main}")
        return 1

    runpy.run_path(str(project_main), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
