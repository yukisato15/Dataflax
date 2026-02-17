#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Compatibility build wrapper for reorganized Dataflux workspace."""

from pathlib import Path
import runpy
import sys


def main() -> int:
    build_script = Path(__file__).resolve().parent / "Dataflux" / "build_dataflux.py"
    if not build_script.exists():
        print(f"Error: build script not found: {build_script}")
        return 1

    runpy.run_path(str(build_script), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
