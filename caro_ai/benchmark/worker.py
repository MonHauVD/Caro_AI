"""Tính nước đi AI trong process pool — chỉ caro + Agent, không pygame."""

from __future__ import annotations

from typing import Any

import caro_ai.game.caro as caro
from caro_ai.ai.agent import Agent


def compute_ai_move_worker(
    game_snapshot: caro.Caro,
    max_depth: int,
    xo: str,
    agent_config: dict[str, Any] | None = None,
) -> list[int] | None:
    worker_agent = Agent(max_depth=max_depth, XO=xo, config=agent_config, log_init=False)
    return worker_agent.get_move(game_snapshot)


def warm_benchmark_worker(_token: int) -> None:
    """Mỗi worker gọi một lần song song để import sẵn module (spawn Windows)."""
    return None
