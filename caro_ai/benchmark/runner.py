"""Chạy một ván benchmark headless (dùng cho multiprocessing, không pygame UI)."""

from __future__ import annotations

import statistics
import time
from typing import Any


def board_to_ascii_from_game(game) -> str:
    return "\n".join(" ".join(row) for row in game.grid)


def _move_time_summary(times: list[float]) -> dict[str, float | int]:
    if not times:
        return {"min": 0.0, "median": 0.0, "max": 0.0, "count": 0}
    return {
        "min": round(float(min(times)), 4),
        "median": round(float(statistics.median(times)), 4),
        "max": round(float(max(times)), 4),
        "count": len(times),
    }


def run_headless_benchmark_game(
    rows: int,
    cols: int,
    winning_condition: int,
    origin_xo: str,
    matchup_name: str,
    agent_a: dict[str, Any],
    agent_b: dict[str, Any],
    game_idx: int,
) -> dict[str, Any]:
    """Chạy đủ một ván AI vs AI; trả về dict có `result_entry` (ghi file) và `merge_stats`."""
    from caro_ai.ai.agent import Agent
    from caro_ai.game.caro import Caro

    swap = (game_idx % 2 == 1)
    x_side = agent_b if swap else agent_a
    o_side = agent_a if swap else agent_b
    x_label = x_side["label"]
    o_label = o_side["label"]

    game = Caro(rows, cols, winning_condition, origin_xo)
    game.reset()
    game.use_ai(True)

    cfg_x = x_side.get("config") or {}
    cfg_o = o_side.get("config") or {}
    agent_x = Agent(max_depth=x_side["depth"], XO="X", config=cfg_x, log_init=False)
    agent_o = Agent(max_depth=o_side["depth"], XO="O", config=cfg_o, log_init=False)

    move_times: dict[str, list[float]] = {x_label: [], o_label: []}
    turn_started = time.perf_counter()
    max_plies = rows * cols + 4

    for _ in range(max_plies):
        w = game.get_winner()
        if w != -1:
            break
        ag = agent_x if game.turn == 1 else agent_o
        label = x_label if game.turn == 1 else o_label
        mv = ag.get_move(game)
        elapsed = time.perf_counter() - turn_started
        if mv is None:
            break
        game.make_move(mv[0], mv[1])
        move_times[label].append(float(elapsed))
        turn_started = time.perf_counter()

    winner = game.get_winner()
    x_stat = {
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "move_time_total": sum(move_times[x_label]),
        "move_count": len(move_times[x_label]),
    }
    o_stat = {
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "move_time_total": sum(move_times[o_label]),
        "move_count": len(move_times[o_label]),
    }
    if winner == 0:
        x_stat["wins"] = 1
        o_stat["losses"] = 1
        winner_label = x_label
    elif winner == 1:
        o_stat["wins"] = 1
        x_stat["losses"] = 1
        winner_label = o_label
    else:
        x_stat["draws"] = 1
        o_stat["draws"] = 1
        winner_label = "draw"

    x_avg = (
        x_stat["move_time_total"] / x_stat["move_count"] if x_stat["move_count"] else 0.0
    )
    o_avg = (
        o_stat["move_time_total"] / o_stat["move_count"] if o_stat["move_count"] else 0.0
    )

    x_cfg = {"depth": x_side["depth"], **dict(cfg_x)}
    o_cfg = {"depth": o_side["depth"], **dict(cfg_o)}
    xt = _move_time_summary(move_times[x_label])
    ot = _move_time_summary(move_times[o_label])

    match_id = f"{matchup_name}__game_{game_idx + 1}"
    result_entry = {
        "match_id": match_id,
        "agent_x": {"label": x_label, "config": x_cfg},
        "agent_o": {"label": o_label, "config": o_cfg},
        "winner_label": winner_label,
        "winner_code": winner,
        "x_avg_move_sec": round(x_avg, 4),
        "o_avg_move_sec": round(o_avg, 4),
        "x_moves": x_stat["move_count"],
        "o_moves": o_stat["move_count"],
        "board_ascii": board_to_ascii_from_game(game),
        "stats_extra": {
            "x_move_time_min_sec": xt["min"],
            "x_move_time_median_sec": xt["median"],
            "x_move_time_max_sec": xt["max"],
            "o_move_time_min_sec": ot["min"],
            "o_move_time_median_sec": ot["median"],
            "o_move_time_max_sec": ot["max"],
        },
    }

    merge_stats = {x_label: x_stat, o_label: o_stat}
    return {"result_entry": result_entry, "merge_stats": merge_stats}
