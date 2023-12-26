#!/usr/bin/env3 python3
# Copyright (c) School of Artificial Intelligence, OPtics and ElectroNics(iOPEN), Northwestern PolyTechnical University. All righs reserved.
# Author: Hongjun An (Coder.AN)
# Email: an.hongjun@foxmail.com

# This file is used for package installation. Script of traditional_process/draw_results will be available.

import sys
from importlib import abc, util
from pathlib import Path

_TOOLS_PATH = Path(__file__).resolve().parent.parent.parent / "scripts"

if _TOOLS_PATH.is_dir():
    # This is true only for in-place installation (pip install -e, setup.py develop),
    # where setup(package_dir=) does not work: https://github.com/pypa/setuptools/issues/230

    class _PathFinder(abc.MetaPathFinder):

        def find_spec(self, name, path, target=None):
            if not name.startswith("streaknet.scripts."):
                return
            project_name = name.split(".")[-1] + ".py"
            target_file = _TOOLS_PATH / project_name
            if not target_file.is_file():
                return
            return util.spec_from_file_location(name, target_file)

    sys.meta_path.append(_PathFinder())