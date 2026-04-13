"""Hàm tiện ích dùng chung cho app (không phụ thuộc pygame loop)."""

from __future__ import annotations

import os
import statistics
import sys

import caro_ai.game.caro as caro


def resolve_config_dir(project_root: str) -> str:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return os.path.join(meipass, "config")
    return os.path.join(project_root, "config")


def resource_path(relative_path: str, project_root: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = project_root
    return os.path.join(base_path, relative_path)


def board_to_ascii(this_game: caro.Caro) -> str:
    return "\n".join(" ".join(row) for row in this_game.grid)


def per_move_timing_summary(times: list[float]) -> dict[str, float]:
    if not times:
        return {"min": 0.0, "median": 0.0, "max": 0.0}
    return {
        "min": round(float(min(times)), 4),
        "median": round(float(statistics.median(times)), 4),
        "max": round(float(max(times)), 4),
    }
