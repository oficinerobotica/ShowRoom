# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""Paths to the workbench resources."""
from os import path

module_path = path.dirname(path.dirname(path.realpath(__file__)))
resources_path = path.join(module_path, 'Resources')
icons_path = path.join(resources_path, 'Icons')


def iconPath(name):
    return path.join(icons_path, name)

