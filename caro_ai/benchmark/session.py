"""Logic benchmark: cấu hình, hàng đợi trận, đa bàn, ghi kết quả."""

from __future__ import annotations

import copy
import glob
import json
import os
import shutil
import sys
import threading
import time
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable

import pygame

from caro_ai import app_helpers
from caro_ai.benchmark import multi as bench_multi
from caro_ai.benchmark.report_merge import (
    FRAGMENT_BOARD_NAME,
    FRAGMENT_MOVES_NAME,
    FRAGMENT_SUMMARY_NAME,
    _ensure_benchmark_result_dirs,
    count_fragment_games,
    export_benchmark_fragments_if_any,
    export_benchmark_merged_reports,
    fragment_subdirectory_name,
    list_fragment_summary_paths_in_order,
)
import caro_ai.game.caro as caro
from caro_ai.ui import buttons as button
from caro_ai.ui.layout import BENCH_PROGRESS_LINE_Y

_append_lock = threading.Lock()

_SKIP_STATS_TOP = frozenset(
    {
        "completion_index",
        "game_seq",
        "x_avg_move_sec",
        "o_avg_move_sec",
        "x_moves",
        "o_moves",
        "winner_code",
        "game_wall_duration_sec",
        "game_moves_time_sec",
    }
)


def load_benchmark_results_from_disk(
    summary_path: str,
    board_path: str,
    moves_path: str | None,
) -> list[dict[str, Any]]:
    """Đọc report đã có để rewrite sau này không làm mất ván cũ (resume / chạy tiếp)."""
    if not os.path.isfile(summary_path) or os.path.getsize(summary_path) == 0:
        return []
    try:
        with open(summary_path, encoding="utf-8") as f:
            sum_text = f.read()
    except OSError:
        return []

    boards_by_match: dict[str, str] = {}
    if os.path.isfile(board_path) and os.path.getsize(board_path) > 0:
        try:
            with open(board_path, encoding="utf-8") as f:
                board_text = f.read()
            for raw in board_text.split("\n\n"):
                b = raw.strip()
                if not b:
                    continue
                lines = b.split("\n")
                mid = None
                bi = None
                for i, line in enumerate(lines):
                    if line.startswith("match_id="):
                        mid = line.split("=", 1)[1].strip()
                    elif (
                        len(line) >= 3
                        and line[0] in ".XO"
                        and " " in line
                        and not line.startswith("agent_")
                    ):
                        bi = i
                        break
                if mid and bi is not None:
                    boards_by_match[mid] = "\n".join(lines[bi:]).strip()
        except OSError:
            pass

    moves_by_match: dict[str, list[str]] = {}
    if moves_path and os.path.isfile(moves_path) and os.path.getsize(moves_path) > 0:
        try:
            with open(moves_path, encoding="utf-8") as f:
                mv_text = f.read()
            for raw in mv_text.split("\n\n"):
                sec = raw.strip()
                if not sec:
                    continue
                sl = [ln for ln in sec.split("\n") if ln.strip()]
                mid = None
                for line in sl:
                    if line.startswith("match_id="):
                        mid = line.split("=", 1)[1].strip()
                        break
                if mid:
                    moves_by_match[mid] = sl
        except OSError:
            pass

    by_seq: dict[int, dict[str, Any]] = {}
    for raw in sum_text.split("\n\n"):
        block = raw.strip()
        if not block:
            continue
        kv: dict[str, str] = {}
        stats_json: str | None = None
        for line in block.split("\n"):
            if line.startswith("stats="):
                stats_json = line[6:]
            elif "=" in line:
                k, v = line.split("=", 1)
                kv[k.strip()] = v.strip()
        if "match_id" not in kv or "agent_x" not in kv or "agent_o" not in kv:
            continue
        mid = kv["match_id"]
        try:
            game_seq = int(kv.get("game_seq", "0"))
        except ValueError:
            game_seq = 0
        try:
            stats_obj: dict[str, Any] = json.loads(stats_json) if stats_json else {}
        except json.JSONDecodeError:
            stats_obj = {}
        try:
            agent_x = json.loads(kv["agent_x"])
            agent_o = json.loads(kv["agent_o"])
        except json.JSONDecodeError:
            continue
        winner_label = kv.get("winner", "draw")
        try:
            wc = int(stats_obj.get("winner_code", -1))
        except (TypeError, ValueError):
            wc = -1
        if wc < 0:
            xl = agent_x.get("label", "")
            ol = agent_o.get("label", "")
            if winner_label == xl:
                wc = 0
            elif winner_label == ol:
                wc = 1
            elif winner_label == "draw":
                wc = 2
            else:
                wc = -1
        gwall = float(
            kv.get("game_wall_duration_sec", stats_obj.get("game_wall_duration_sec", 0.0))
            or 0.0
        )
        gmoves = float(
            kv.get("game_moves_time_sec", stats_obj.get("game_moves_time_sec", 0.0)) or 0.0
        )
        stats_extra = {
            k: v for k, v in stats_obj.items() if k not in _SKIP_STATS_TOP
        }
        entry: dict[str, Any] = {
            "match_id": mid,
            "game_seq": game_seq,
            "completion_index": int(stats_obj.get("completion_index", 0) or 0),
            "agent_x": agent_x,
            "agent_o": agent_o,
            "winner_label": winner_label,
            "winner_code": wc,
            "x_avg_move_sec": float(stats_obj.get("x_avg_move_sec", 0.0)),
            "o_avg_move_sec": float(stats_obj.get("o_avg_move_sec", 0.0)),
            "x_moves": int(stats_obj.get("x_moves", 0)),
            "o_moves": int(stats_obj.get("o_moves", 0)),
            "game_wall_duration_sec": round(gwall, 4),
            "game_moves_time_sec": round(gmoves, 4),
            "board_ascii": boards_by_match.get(mid, ""),
            "move_lines": moves_by_match.get(mid, []),
            "stats_extra": stats_extra,
        }
        if game_seq > 0:
            by_seq[game_seq] = entry

    out = sorted(by_seq.values(), key=lambda r: r["game_seq"])
    if out:
        print(f"[BENCH] loaded {len(out)} result block(s) from disk for ordered rewrite")
    return out


@dataclass
class BenchRuntime:
    get_executor: Callable[[], ProcessPoolExecutor | None]
    set_executor: Callable[[ProcessPoolExecutor | None], None]
    compute_ai_move_worker: Callable[..., list[int] | None]
    ai_thinking_btn: button.Button
    set_ai_is_thinking: Callable[[bool], None]


def _benchmark_matchup_side_label_ref(side: Any) -> str | None:
    """Trả về tên label nếu cần tra `custom_agents`; None nếu agent đã khai báo đầy đủ (có depth)."""
    if isinstance(side, str):
        s = side.strip()
        return s if s else None
    if isinstance(side, dict):
        if "depth" in side:
            return None
        lab = side.get("label")
        if isinstance(lab, str) and lab.strip():
            return lab.strip()
    return None


def _benchmark_resolve_agent_from_custom(label: str, custom_agents: dict[str, Any]) -> dict[str, Any]:
    tpl = custom_agents.get(label)
    if not isinstance(tpl, dict):
        raise ValueError(f'custom_agents[{label!r}] must be an object with depth/config')
    out = copy.deepcopy(tpl)
    out["label"] = label
    if "depth" not in out:
        raise ValueError(f'custom_agents[{label!r}] must include "depth"')
    return out


def normalize_benchmark_setup(benchmark_setup: dict) -> None:
    """Mở rộng matchups: agent chỉ có label → copy từ custom_agents (giữ tương thích JSON cũ có agent đầy đủ)."""
    matchups = benchmark_setup.get("matchups")
    if not isinstance(matchups, list):
        return
    custom_agents = benchmark_setup.get("custom_agents")
    if not isinstance(custom_agents, dict):
        custom_agents = {}

    for m in matchups:
        if not isinstance(m, dict):
            continue
        mn = m.get("name")
        mname = mn if isinstance(mn, str) else "?"
        for side_key in ("agent_a", "agent_b"):
            side = m.get(side_key)
            if side is None:
                raise ValueError(f'matchup {mname!r}: missing {side_key}')
            if isinstance(side, dict) and "depth" in side:
                m[side_key] = copy.deepcopy(side)
                continue
            lab = _benchmark_matchup_side_label_ref(side)
            if lab is None:
                raise ValueError(
                    f'matchup {mname!r}: {side_key} must be a label string, '
                    f'{{"label": "<id>"}}, or an inline object with "depth"'
                )
            if not custom_agents:
                raise ValueError(
                    f'matchup {mname!r}: {side_key} references label {lab!r} but '
                    f'"custom_agents" is missing or not an object'
                )
            m[side_key] = _benchmark_resolve_agent_from_custom(lab, custom_agents)


def load_benchmark_config(
    benchmark_setup: dict,
    config_path: str | None = None,
    *,
    default_config_file: str,
    must_exist: bool = False,
) -> None:
    path = config_path or default_config_file
    if not os.path.isfile(path):
        if must_exist:
            print(f"[BENCH] error: config not found: {path}", file=sys.stderr)
            sys.exit(2)
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            benchmark_setup.update(loaded)
            normalize_benchmark_setup(benchmark_setup)
            print(f"[BENCH] loaded config from {path}")
    except Exception as ex:
        print(f"[BENCH] failed to load config file {path}: {ex}", file=sys.stderr)
        if must_exist:
            sys.exit(2)


def _parse_match_id(match_id: str) -> tuple[str, int] | None:
    if "__game_" not in match_id:
        return None
    matchup_name, game_part = match_id.rsplit("__game_", 1)
    try:
        game_no = int(game_part)
    except Exception:
        return None
    return matchup_name, game_no


def _collect_completed_match_games(
    benchmark_setup: dict,
    summary_path: str,
    fragments_dir: str | None = None,
) -> tuple[set[tuple[str, int]], int]:
    """Thu thập tập (matchup_name, game_no) đã hoàn tất từ fragments hoặc summary."""
    matchups = benchmark_setup.get("matchups", [])
    games_per_matchup = max(1, int(benchmark_setup.get("games_per_matchup", 1)))
    if not matchups:
        return set(), 0

    matchup_name_to_idx: dict[str, int] = {}
    for idx, matchup in enumerate(matchups):
        name = matchup.get("name")
        if isinstance(name, str) and name != "":
            matchup_name_to_idx[name] = idx

    frag = fragments_dir or os.path.join(os.path.dirname(summary_path), "fragments")
    frag_summaries = list_fragment_summary_paths_in_order(frag)

    completed: set[tuple[str, int]] = set()
    ignored_count = 0

    def _ingest_match_line(line: str) -> None:
        nonlocal ignored_count
        if not line.startswith("match_id="):
            return
        match_id = line.split("=", 1)[1].strip()
        parsed = _parse_match_id(match_id)
        if parsed is None:
            ignored_count += 1
            return
        matchup_name, game_no = parsed
        matchup_idx = matchup_name_to_idx.get(matchup_name)
        if matchup_idx is None:
            ignored_count += 1
            return
        if game_no < 1 or game_no > games_per_matchup:
            ignored_count += 1
            return
        completed.add((matchup_name, game_no))

    try:
        if frag_summaries:
            for fp in frag_summaries:
                try:
                    with open(fp, encoding="utf-8") as f:
                        for raw_line in f:
                            _ingest_match_line(raw_line.strip())
                except OSError:
                    pass
        elif os.path.exists(summary_path):
            with open(summary_path, encoding="utf-8") as f:
                for raw_line in f:
                    _ingest_match_line(raw_line.strip())
    except Exception as ex:
        print(f"[BENCH] failed to inspect summary/fragments for resume: {ex}")
        return set(), 0

    return completed, ignored_count


def detect_benchmark_resume_position(
    benchmark_setup: dict,
    summary_path: str,
    fragments_dir: str | None = None,
) -> tuple[int, int]:
    matchups = benchmark_setup.get("matchups", [])
    games_per_matchup = max(1, int(benchmark_setup.get("games_per_matchup", 1)))
    if not matchups:
        return 0, 0

    completed, ignored_count = _collect_completed_match_games(
        benchmark_setup, summary_path, fragments_dir
    )

    if ignored_count > 0:
        print(f"[BENCH] ignored {ignored_count} summary entries not in current config or invalid")

    if not completed:
        print("[BENCH] no valid previous result found; start from first game")
        return 0, 0

    for mi, matchup in enumerate(matchups):
        mn = matchup.get("name")
        if not isinstance(mn, str):
            continue
        for gi in range(games_per_matchup):
            if (mn, gi + 1) not in completed:
                print(f"[BENCH] resume next game at matchup_idx={mi}, game_idx={gi}")
                return mi, gi

    print("[BENCH] previous run already reached end of configured matchups; start from first game")
    return 0, 0


def _benchmark_build_stats_block(result: dict) -> dict:
    block = {
        "completion_index": result.get("completion_index", 0),
        "game_seq": result.get("game_seq", 0),
        "x_avg_move_sec": result["x_avg_move_sec"],
        "o_avg_move_sec": result["o_avg_move_sec"],
        "x_moves": result["x_moves"],
        "o_moves": result["o_moves"],
        "winner_code": result["winner_code"],
        "game_wall_duration_sec": result.get("game_wall_duration_sec", 0.0),
        "game_moves_time_sec": result.get("game_moves_time_sec", 0.0),
    }
    extra = result.get("stats_extra")
    if extra:
        block.update(extra)
    return block


def benchmark_game_seq_from_mi_gi(benchmark_setup: dict, mi: int, gi: int) -> int:
    """Thứ tự ván trong config: cặp 0 ván 0 → 1, … (games_per_matchup cố định mọi cặp)."""
    gpm = max(1, int(benchmark_setup.get("games_per_matchup", 1)))
    return mi * gpm + gi + 1


def benchmark_total_games_planned(benchmark_setup: dict) -> int:
    """Tổng số ván theo config (dùng hiển thị game_seq/total)."""
    gpm = max(1, int(benchmark_setup.get("games_per_matchup", 1)))
    return len(benchmark_setup.get("matchups", [])) * gpm


def benchmark_on_new_game_begin(
    benchmark_state: dict, current: dict | None, game_seq: int
) -> None:
    """Mốc thời gian tường + game_seq cố định theo thứ tự config (không theo thứ tự kết thúc)."""
    if current is None:
        return
    current["game_started_at"] = time.perf_counter()
    current["game_seq"] = int(game_seq)
    current["move_log_lines"] = []


def build_benchmark_task_queue(
    benchmark_setup: dict, start_mi: int, start_gi: int
) -> list[tuple[int, int, int]]:
    """(game_seq, matchup_idx, game_idx) theo đúng thứ tự trong config."""
    matchups = benchmark_setup["matchups"]
    gpm = max(1, int(benchmark_setup.get("games_per_matchup", 1)))
    q: list[tuple[int, int, int]] = []
    for mi in range(start_mi, len(matchups)):
        g0 = start_gi if mi == start_mi else 0
        for gi in range(g0, gpm):
            seq = benchmark_game_seq_from_mi_gi(benchmark_setup, mi, gi)
            q.append((seq, mi, gi))
    return q


def build_benchmark_missing_task_queue(
    benchmark_setup: dict, completed: set[tuple[str, int]]
) -> list[tuple[int, int, int]]:
    """Queue chỉ chứa các ván còn thiếu dựa trên tập (matchup_name, game_no) đã hoàn tất."""
    matchups = benchmark_setup["matchups"]
    gpm = max(1, int(benchmark_setup.get("games_per_matchup", 1)))
    q: list[tuple[int, int, int]] = []
    for mi, matchup in enumerate(matchups):
        mn = matchup.get("name")
        if not isinstance(mn, str):
            continue
        for gi in range(gpm):
            if (mn, gi + 1) in completed:
                continue
            seq = benchmark_game_seq_from_mi_gi(benchmark_setup, mi, gi)
            q.append((seq, mi, gi))
    return q


def ensure_benchmark_slots(
    benchmark_state: dict,
    n: int,
    rownum: int,
    colnum: int,
    winning_condition: int,
    xo: str,
) -> None:
    if benchmark_state.get("bench_slots_n") == n and len(benchmark_state.get("slots", [])) == n:
        return
    benchmark_state["slots"] = [
        bench_multi.create_slot(i, rownum, colnum, winning_condition, xo) for i in range(n)
    ]
    benchmark_state["bench_slots_n"] = n
    if not isinstance(benchmark_state.get("task_queue"), deque):
        benchmark_state["task_queue"] = deque()


def _benchmark_cancel_slot_future(slot: dict) -> None:
    fut = slot.get("dev_future")
    if fut is not None:
        fut.cancel()
    slot["dev_future"] = None


def _snapshot_slot_turn_clock(slot: dict) -> None:
    if slot.get("current") is None or slot.get("status") != -1:
        return
    t0 = slot.get("turn_started_at")
    if t0 is None:
        slot["turn_elapsed_snapshot"] = 0.0
    else:
        slot["turn_elapsed_snapshot"] = max(0.0, time.perf_counter() - t0)


def _resume_slot_turn_clock(slot: dict) -> None:
    """Sau resume: đồng hồ nước đi bắt đầu khi submit job (xem benchmark_multi_tick_slots)."""
    slot["turn_started_at"] = None
    slot["turn_elapsed_snapshot"] = 0.0


def make_matchup_setup(benchmark_setup: dict, mi: int, gi: int, game: caro.Caro):
    return bench_multi.make_matchup_setup(benchmark_setup["matchups"][mi], gi, game)


def benchmark_finalize_from_game(
    benchmark_setup: dict,
    benchmark_state: dict,
    summary_path: str,
    board_path: str,
    game: caro.Caro,
    current: dict | None,
    *,
    bump_parallel_done: bool = False,
) -> None:
    if current is None:
        return
    winner = game.get_winner()
    x_label = current["x_label"]
    o_label = current["o_label"]
    if winner == 0:
        current["stats"][x_label]["wins"] += 1
        current["stats"][o_label]["losses"] += 1
    elif winner == 1:
        current["stats"][o_label]["wins"] += 1
        current["stats"][x_label]["losses"] += 1
    else:
        current["stats"][x_label]["draws"] += 1
        current["stats"][o_label]["draws"] += 1

    matchup_name = current["matchup_name"]
    if matchup_name not in benchmark_state["stats"]:
        benchmark_state["stats"][matchup_name] = {}
    for label, s in current["stats"].items():
        if label not in benchmark_state["stats"][matchup_name]:
            benchmark_state["stats"][matchup_name][label] = bench_multi.new_agent_stats()
        agg = benchmark_state["stats"][matchup_name][label]
        agg["wins"] += s["wins"]
        agg["losses"] += s["losses"]
        agg["draws"] += s["draws"]
        agg["move_time_total"] += s["move_time_total"]
        agg["move_count"] += s["move_count"]

    x_stat = current["stats"][x_label]
    o_stat = current["stats"][o_label]
    x_avg = (x_stat["move_time_total"] / x_stat["move_count"]) if x_stat["move_count"] else 0.0
    o_avg = (o_stat["move_time_total"] / o_stat["move_count"]) if o_stat["move_count"] else 0.0

    if winner == 0:
        winner_label = x_label
    elif winner == 1:
        winner_label = o_label
    else:
        winner_label = "draw"

    match_id = f"{matchup_name}__game_{current['game_idx'] + 1}"
    x_times = x_stat.get("move_times") or []
    o_times = o_stat.get("move_times") or []
    xt = app_helpers.per_move_timing_summary(x_times)
    ot = app_helpers.per_move_timing_summary(o_times)
    game_moves_time_sec = round(float(x_stat["move_time_total"] + o_stat["move_time_total"]), 4)
    t0 = current.get("game_started_at")
    if t0 is not None:
        game_wall_duration_sec = round(max(0.0, time.perf_counter() - float(t0)), 4)
    else:
        game_wall_duration_sec = game_moves_time_sec
    game_seq = int(current.get("game_seq", 0))
    result_entry = {
        "match_id": match_id,
        "game_seq": game_seq,
        "agent_x": {"label": x_label, "config": current["x_config"]},
        "agent_o": {"label": o_label, "config": current["o_config"]},
        "winner_label": winner_label,
        "winner_code": winner,
        "x_avg_move_sec": round(x_avg, 4),
        "o_avg_move_sec": round(o_avg, 4),
        "x_moves": x_stat["move_count"],
        "o_moves": o_stat["move_count"],
        "game_wall_duration_sec": game_wall_duration_sec,
        "game_moves_time_sec": game_moves_time_sec,
        "board_ascii": app_helpers.board_to_ascii(game),
        "stats_extra": {
            "x_move_time_min_sec": xt["min"],
            "x_move_time_median_sec": xt["median"],
            "x_move_time_max_sec": xt["max"],
            "o_move_time_min_sec": ot["min"],
            "o_move_time_median_sec": ot["median"],
            "o_move_time_max_sec": ot["max"],
        },
    }
    result_entry["move_lines"] = list(current.get("move_log_lines") or [])
    moves_path = benchmark_state.get("_moves_path")
    with _append_lock:
        _write_benchmark_game_fragments(
            result_entry,
            summary_path,
            board_path,
            moves_path,
            benchmark_state,
        )
    maybe_periodic_export_benchmark_merged(
        benchmark_setup,
        summary_path,
        board_path,
        moves_path,
        benchmark_state,
    )
    if bump_parallel_done:
        benchmark_state["parallel_done"] = benchmark_state.get("parallel_done", 0) + 1
        print(f"[BENCH] xong {match_id} ({benchmark_state['parallel_done']}/{benchmark_state['parallel_total']})")


def benchmark_multi_setup_slot(
    benchmark_setup: dict,
    slot: dict,
    mi: int,
    gi: int,
    *,
    game_seq: int | None = None,
) -> None:
    a1, a2, cur = make_matchup_setup(benchmark_setup, mi, gi, slot["game"])
    slot["agent1"] = a1
    slot["agent2"] = a2
    slot["current"] = cur
    slot["matchup_idx"] = mi
    slot["game_idx"] = gi
    slot["status"] = slot["game"].get_winner()
    slot["turn_started_at"] = None
    slot["turn_elapsed_snapshot"] = 0.0
    slot["game_ended_at"] = None
    slot["end_finalize_done"] = False
    _benchmark_cancel_slot_future(slot)
    mn = benchmark_setup["matchups"][mi]["name"]
    slot["title"] = f"{mn} — ván {gi + 1}"
    total_pairs = len(benchmark_setup["matchups"])
    gpm = max(1, int(benchmark_setup.get("games_per_matchup", 1)))
    gseq = (
        int(game_seq)
        if game_seq is not None
        else benchmark_game_seq_from_mi_gi(benchmark_setup, mi, gi)
    )
    total_games = benchmark_total_games_planned(benchmark_setup)
    slot["bench_game_seq"] = gseq
    slot["bench_total_games"] = total_games
    match_id = f"{mn}__game_{gi + 1}"
    print(
        f"[BENCH][bàn {slot['id'] + 1}] match_id={match_id} game_seq={gseq}/{total_games} "
        f"(cặp {mi + 1}/{total_pairs}, ván {gi + 1}/{gpm})"
    )


def benchmark_multi_assign_next(benchmark_setup: dict, benchmark_state: dict, slot: dict) -> None:
    q = benchmark_state["task_queue"]
    if not q:
        slot["running"] = False
        slot["paused"] = True
        slot["current"] = None
        slot["title"] = f"Xong — bàn {slot['id'] + 1}"
        slot["bench_game_seq"] = None
        slot["bench_total_games"] = benchmark_total_games_planned(benchmark_setup)
        slot["turn_started_at"] = None
        return
    game_seq, mi, gi = q.popleft()
    benchmark_multi_setup_slot(benchmark_setup, slot, mi, gi, game_seq=game_seq)
    benchmark_on_new_game_begin(benchmark_state, slot["current"], game_seq)


def benchmark_multi_try_finish_run(benchmark_setup: dict, benchmark_state: dict, rt: BenchRuntime) -> None:
    if not benchmark_state.get("bench_session_started"):
        return
    if benchmark_state["task_queue"]:
        return
    for s in benchmark_state["slots"]:
        if s["running"]:
            return
        if s["dev_future"] is not None:
            return
        if s["game_ended_at"] is not None:
            return
        if s["current"] is not None and s["status"] == -1:
            return
    benchmark_multi_on_all_complete(benchmark_setup, benchmark_state, rt)


def benchmark_multi_on_all_complete(benchmark_setup: dict, benchmark_state: dict, rt: BenchRuntime) -> None:
    benchmark_state["running"] = False
    benchmark_state["bench_session_started"] = False
    benchmark_state["bench_paused"] = False
    benchmark_state["matchup_idx"] = len(benchmark_setup["matchups"])
    benchmark_state["game_idx"] = 0
    rt.set_ai_is_thinking(False)
    rt.ai_thinking_btn.disable_button()
    print("[BENCH] completed all matchups (multi-board)")
    for matchup_name, matchup_stats in benchmark_state["stats"].items():
        print(f"[BENCH][{matchup_name}]")
        for label, s in matchup_stats.items():
            avg = (s["move_time_total"] / s["move_count"]) if s["move_count"] else 0.0
            print(f"  {label}: W={s['wins']} L={s['losses']} D={s['draws']} avg_move={avg:.3f}s")
    sp = benchmark_state.get("_summary_path")
    if sp:
        export_benchmark_merged_reports(
            sp,
            benchmark_state.get("_board_path", ""),
            benchmark_state.get("_moves_path"),
            benchmark_state.get("_fragments_dir")
            or os.path.join(os.path.dirname(sp), "fragments"),
        )


def benchmark_warm_executor(ex: ProcessPoolExecutor | None, n_workers: int) -> None:
    """Submit N job rỗng song song để mỗi process worker import sẵn worker/caro/agent (spawn Windows)."""
    if ex is None or n_workers < 1:
        return
    from caro_ai.benchmark.worker import warm_benchmark_worker

    futs = [ex.submit(warm_benchmark_worker, i) for i in range(n_workers)]
    for f in futs:
        f.result()


def benchmark_multi_resize_executor(rt: BenchRuntime, n_workers: int) -> None:
    ex = rt.get_executor()
    if ex is not None:
        ex.shutdown(wait=False, cancel_futures=True)
    nw = max(1, n_workers)
    new_ex = ProcessPoolExecutor(max_workers=nw)
    rt.set_executor(new_ex)
    benchmark_warm_executor(new_ex, nw)


def benchmark_multi_start_all(benchmark_setup: dict, benchmark_state: dict, rt: BenchRuntime) -> None:
    n = benchmark_state["parallel_workers"]
    print(f"[BENCH][UI] Start chung: bench_paused={benchmark_state.get('bench_paused')}, session_started={benchmark_state.get('bench_session_started')}")

    if benchmark_state.get("bench_paused"):
        benchmark_state["bench_paused"] = False
        benchmark_state["running"] = True
        benchmark_state["bench_session_started"] = True
        benchmark_multi_resize_executor(rt, len(benchmark_state["slots"]))
        for s in benchmark_state["slots"]:
            if s["current"] is not None:
                s["paused"] = False
                s["running"] = True
                _resume_slot_turn_clock(s)
        rt.ai_thinking_btn.enable_button()
        print("[BENCH][UI] Resume chung sau Pause (giữ hàng đợi và ván hiện tại).")
        return

    ensure_benchmark_slots(
        benchmark_state,
        n,
        benchmark_state.get("_rownum", 18),
        benchmark_state.get("_colnum", 20),
        benchmark_state.get("_winning_condition", 5),
        benchmark_state.get("_xo", "X"),
    )
    rmi, rgi = detect_benchmark_resume_position(
        benchmark_setup,
        benchmark_state.get("_summary_path", ""),
        benchmark_state.get("_fragments_dir"),
    )
    benchmark_state["resume_matchup_idx"] = rmi
    benchmark_state["resume_game_idx"] = rgi
    completed, ignored_count = _collect_completed_match_games(
        benchmark_setup,
        benchmark_state.get("_summary_path", ""),
        benchmark_state.get("_fragments_dir"),
    )
    if ignored_count > 0:
        print(f"[BENCH] ignored {ignored_count} summary entries not in current config or invalid")
    q = build_benchmark_missing_task_queue(benchmark_setup, completed)
    benchmark_state["task_queue"] = deque(q)
    benchmark_state["parallel_total"] = len(q)
    benchmark_state["parallel_done"] = 0
    benchmark_state["stats"] = {}
    benchmark_state["results"] = []
    benchmark_state["bench_session_started"] = True
    benchmark_state["bench_paused"] = False
    benchmark_multi_resize_executor(rt, len(benchmark_state["slots"]))
    for s in benchmark_state["slots"]:
        s["paused"] = False
        s["running"] = True
        benchmark_multi_assign_next(benchmark_setup, benchmark_state, s)
    benchmark_state["running"] = True
    rt.ai_thinking_btn.enable_button()
    print(f"[BENCH][UI] Phiên mới: {len(q)} ván trong hàng đợi, {len(benchmark_state['slots'])} bàn.")


def benchmark_multi_pause_all(benchmark_state: dict, rt: BenchRuntime) -> None:
    print("[BENCH][UI] Pause chung")
    benchmark_state["running"] = False
    benchmark_state["bench_paused"] = True
    for s in benchmark_state["slots"]:
        _snapshot_slot_turn_clock(s)
        s["paused"] = True
        s["running"] = False
        _benchmark_cancel_slot_future(s)
    ex = rt.get_executor()
    if ex is not None:
        ex.shutdown(wait=False, cancel_futures=True)
        rt.set_executor(None)


def benchmark_multi_global_replay(benchmark_setup: dict, benchmark_state: dict, rt: BenchRuntime) -> None:
    print("[BENCH][UI] Replay chung")
    benchmark_multi_pause_all(benchmark_state, rt)
    ensure_benchmark_slots(
        benchmark_state,
        benchmark_state["parallel_workers"],
        benchmark_state.get("_rownum", 18),
        benchmark_state.get("_colnum", 20),
        benchmark_state.get("_winning_condition", 5),
        benchmark_state.get("_xo", "X"),
    )
    benchmark_multi_resize_executor(rt, len(benchmark_state["slots"]))
    for slot in benchmark_state["slots"]:
        if slot["current"] is not None:
            mi, gi = slot["matchup_idx"], slot["game_idx"]
            gseq = benchmark_game_seq_from_mi_gi(benchmark_setup, mi, gi)
            benchmark_multi_setup_slot(benchmark_setup, slot, mi, gi, game_seq=gseq)
            benchmark_on_new_game_begin(benchmark_state, slot["current"], gseq)
            slot["running"] = True
            slot["paused"] = False
        else:
            slot["paused"] = True
            slot["running"] = False
    benchmark_state["bench_paused"] = False
    benchmark_state["running"] = any(s["current"] is not None for s in benchmark_state["slots"])
    benchmark_state["bench_session_started"] = benchmark_state["running"]
    if benchmark_state["running"]:
        rt.ai_thinking_btn.enable_button()
    print("[BENCH] Replay chung: chơi lại ván hiện tại trên mỗi bàn có trận")


def benchmark_slot_start(benchmark_setup: dict, benchmark_state: dict, rt: BenchRuntime, slot: dict) -> None:
    sid = slot["id"] + 1
    print(
        f"[BENCH][UI] Start bàn {sid}: current={'yes' if slot['current'] else 'no'}, "
        f"queue_len={len(benchmark_state['task_queue'])}, paused={slot.get('paused')}, running={slot.get('running')}"
    )
    if slot["current"] is None:
        if benchmark_state["task_queue"]:
            slot["paused"] = False
            slot["running"] = True
            benchmark_multi_assign_next(benchmark_setup, benchmark_state, slot)
            if rt.get_executor() is None:
                benchmark_multi_resize_executor(rt, len(benchmark_state["slots"]))
            benchmark_state["bench_session_started"] = True
            benchmark_state["bench_paused"] = False
    else:
        slot["paused"] = False
        slot["running"] = True
        _resume_slot_turn_clock(slot)
        if rt.get_executor() is None:
            benchmark_multi_resize_executor(rt, len(benchmark_state["slots"]))
        benchmark_state["bench_session_started"] = True
        benchmark_state["bench_paused"] = False


def benchmark_slot_pause(benchmark_state: dict, rt: BenchRuntime, slot: dict) -> None:
    print(f"[BENCH][UI] Pause bàn {slot['id'] + 1}")
    _snapshot_slot_turn_clock(slot)
    slot["paused"] = True
    slot["running"] = False
    _benchmark_cancel_slot_future(slot)
    if rt.get_executor() is not None and not any(s["running"] for s in benchmark_state["slots"]):
        ex = rt.get_executor()
        if ex is not None:
            ex.shutdown(wait=False, cancel_futures=True)
            rt.set_executor(None)


def benchmark_slot_replay(benchmark_setup: dict, benchmark_state: dict, rt: BenchRuntime, slot: dict) -> None:
    print(f"[BENCH][UI] Replay bàn {slot['id'] + 1}")
    if slot["current"] is None:
        return
    mi, gi = slot["matchup_idx"], slot["game_idx"]
    gseq = benchmark_game_seq_from_mi_gi(benchmark_setup, mi, gi)
    benchmark_multi_setup_slot(benchmark_setup, slot, mi, gi, game_seq=gseq)
    benchmark_on_new_game_begin(benchmark_state, slot["current"], gseq)
    slot["running"] = True
    slot["paused"] = False
    if rt.get_executor() is None:
        benchmark_multi_resize_executor(rt, len(benchmark_state["slots"]))
    benchmark_state["bench_paused"] = False
    benchmark_state["bench_session_started"] = True


def benchmark_multi_tick_slots(
    benchmark_setup: dict,
    benchmark_state: dict,
    rt: BenchRuntime,
) -> None:
    for slot in benchmark_state["slots"]:
        if slot["current"] is None:
            continue
        if not slot["running"] or slot["paused"]:
            fut = slot.get("dev_future")
            if fut is not None:
                if fut.done():
                    try:
                        fut.result(timeout=0)
                    except Exception:
                        pass
                else:
                    fut.cancel()
                slot["dev_future"] = None
            continue
        if slot["status"] == -1:
            if slot["dev_future"] is None:
                ex = rt.get_executor()
                if ex is None:
                    continue
                snapshot = copy.deepcopy(slot["game"])
                ag = slot["agent1"] if slot["game"].turn == 1 else slot["agent2"]
                slot["turn_started_at"] = time.perf_counter()
                slot["dev_future"] = ex.submit(
                    rt.compute_ai_move_worker,
                    snapshot,
                    ag.max_depth,
                    ag.XO,
                    ag.get_runtime_config(),
                )
            elif slot["dev_future"].done():
                try:
                    best_move = slot["dev_future"].result()
                    if best_move is not None:
                        actor = (
                            slot["current"]["x_label"]
                            if slot["game"].turn == 1
                            else slot["current"]["o_label"]
                        )
                        br, bc = best_move[0], best_move[1]
                        elapsed, moved_piece = bench_multi.apply_move_slot(
                            slot, br, bc, actor, log=True
                        )
                        if elapsed is not None:
                            benchmark_record_move(
                                benchmark_state,
                                actor,
                                elapsed,
                                current=slot["current"],
                                row=br,
                                col=bc,
                                piece=moved_piece,
                            )
                        slot["status"] = slot["game"].get_winner()
                finally:
                    slot["dev_future"] = None
        else:
            if not slot["end_finalize_done"]:
                benchmark_finalize_from_game(
                    benchmark_setup,
                    benchmark_state,
                    benchmark_state["_summary_path"],
                    benchmark_state["_board_path"],
                    slot["game"],
                    slot["current"],
                    bump_parallel_done=True,
                )
                slot["end_finalize_done"] = True
                slot["game_ended_at"] = time.perf_counter()
            elif time.perf_counter() - slot["game_ended_at"] > 0.8:
                slot["game_ended_at"] = None
                slot["end_finalize_done"] = False
                benchmark_multi_assign_next(benchmark_setup, benchmark_state, slot)
    benchmark_multi_try_finish_run(benchmark_setup, benchmark_state, rt)


def _slot_timer_label(slot: dict) -> str:
    g = slot["game"]
    if slot["current"] is None:
        return "—"
    if slot["status"] != -1:
        return f"{g.XO}: —"
    if not slot["running"] or slot["paused"]:
        return f"{g.XO}: {float(slot.get('turn_elapsed_snapshot', 0.0)):.1f}s"
    t0 = slot.get("turn_started_at")
    if t0 is None:
        return f"{g.XO}: 0.0s"
    return f"{g.XO}: {time.perf_counter() - t0:.1f}s"


def draw_benchmark_multi_screen(
    screen: pygame.Surface,
    benchmark_state: dict,
    *,
    black: tuple,
    white: tuple,
    green: tuple,
    red: tuple,
    blue: tuple,
) -> None:
    screen.fill(black)
    font = pygame.font.Font("freesansbold.ttf", 18)
    prog = (
        f"Tiến độ phiên: {benchmark_state['parallel_done']}/{benchmark_state['parallel_total']}"
    )
    screen.blit(font.render(prog, True, white), (12, BENCH_PROGRESS_LINE_Y))
    for slot in benchmark_state["slots"]:
        outer = slot["rect_outer"]
        pygame.draw.rect(screen, blue, outer, 1)
        t = font.render(slot["title"][:70], True, white)
        screen.blit(t, (outer.x + 4, outer.y + 2))
        gs = slot.get("bench_game_seq")
        gt = int(slot.get("bench_total_games") or 0)
        if gs is not None and gt > 0:
            seq_txt = f"{gs}/{gt}"
        else:
            seq_txt = "—"
        seq_surf = font.render(seq_txt, True, white)
        screen.blit(seq_surf, (outer.right - seq_surf.get_width() - 6, outer.y + 22))
        bench_multi.draw_slot_board(slot, screen, white=white, green=green)
        timer_txt = _slot_timer_label(slot)
        screen.blit(
            font.render(timer_txt, True, white),
            (outer.right - 140, outer.y + 46),
        )
        cx = slot["board_rect"].centerx
        cy = slot["board_rect"].centery
        if slot["status"] == 2:
            msg = font.render("Hòa", True, green)
            screen.blit(msg, msg.get_rect(center=(cx, cy)))
        elif slot["status"] == 0:
            msg = font.render("X thắng", True, red)
            screen.blit(msg, msg.get_rect(center=(cx, cy)))
        elif slot["status"] == 1:
            msg = font.render("O thắng", True, blue)
            screen.blit(msg, msg.get_rect(center=(cx, cy)))


def handle_benchmark_multi_ui_frame(
    screen: pygame.Surface,
    benchmark_setup: dict,
    benchmark_state: dict,
    rt: BenchRuntime,
    *,
    start_button: button.Button,
    pause_button: button.Button,
    replay_button: button.Button,
    exit_button: button.Button,
) -> bool:
    if start_button.draw(screen):
        benchmark_multi_start_all(benchmark_setup, benchmark_state, rt)
    if pause_button.draw(screen):
        benchmark_multi_pause_all(benchmark_state, rt)
    if replay_button.draw(screen):
        benchmark_multi_global_replay(benchmark_setup, benchmark_state, rt)
    if exit_button.draw(screen):
        print("[BENCH][UI] Exit chung")
        return True
    for slot in benchmark_state["slots"]:
        bs = slot.get("btn_start")
        if not bs:
            continue
        if bs.draw(screen):
            benchmark_slot_start(benchmark_setup, benchmark_state, rt, slot)
        if slot["btn_pause"].draw(screen):
            benchmark_slot_pause(benchmark_state, rt, slot)
        if slot["btn_replay"].draw(screen):
            benchmark_slot_replay(benchmark_setup, benchmark_state, rt, slot)
    return False


def _summary_block_text(result: dict, completion_index: int) -> str:
    r = {**result, "completion_index": completion_index}
    lines = [
        f"completion_index={completion_index}",
        f"game_seq={result.get('game_seq', 0)}",
        f"match_id={result['match_id']}",
        f"agent_x={json.dumps(result['agent_x'], ensure_ascii=False)}",
        f"agent_o={json.dumps(result['agent_o'], ensure_ascii=False)}",
        f"winner={result['winner_label']}",
        f"game_wall_duration_sec={result.get('game_wall_duration_sec', 0.0)}",
        f"game_moves_time_sec={result.get('game_moves_time_sec', 0.0)}",
        "stats=" + json.dumps(_benchmark_build_stats_block(r), ensure_ascii=False),
        f"board_ref={result['match_id']}",
    ]
    return "\n".join(lines) + "\n"


def _board_block_text(result: dict, completion_index: int) -> str:
    r = result
    lines = [
        f"completion_index={completion_index}",
        f"game_seq={r.get('game_seq', 0)}",
        f"match_id={r['match_id']}",
        f"winner={r['winner_label']}",
        f"agent_x={json.dumps(r['agent_x'], ensure_ascii=False)}",
        f"agent_o={json.dumps(r['agent_o'], ensure_ascii=False)}",
    ]
    if r["winner_label"] == "draw":
        lines += ["result_for_agent_x=draw", "result_for_agent_o=draw"]
    else:
        x_label = r["agent_x"]["label"]
        o_label = r["agent_o"]["label"]
        lines.append(f"result_for_agent_x={'win' if r['winner_label'] == x_label else 'loss'}")
        lines.append(f"result_for_agent_o={'win' if r['winner_label'] == o_label else 'loss'}")
    lines.append(r["board_ascii"])
    return "\n".join(lines) + "\n"


def _write_benchmark_game_fragments(
    result_entry: dict,
    summary_path: str,
    board_path: str,
    moves_path: str | None,
    benchmark_state: dict,
) -> None:
    """Mỗi ván xong ghi thư mục fragments/<game_seq>_<match_id>/summary|board|moves.txt."""
    frag = benchmark_state.get("_fragments_dir") or os.path.join(
        os.path.dirname(summary_path), "fragments"
    )
    os.makedirs(frag, exist_ok=True)
    _ensure_benchmark_result_dirs(summary_path, board_path, moves_path or "")
    seq = int(result_entry["game_seq"])
    mid = str(result_entry.get("match_id", "match"))
    sub = fragment_subdirectory_name(seq, mid)
    game_dir = os.path.join(frag, sub)
    os.makedirs(game_dir, exist_ok=True)
    sp = os.path.join(game_dir, FRAGMENT_SUMMARY_NAME)
    bp = os.path.join(game_dir, FRAGMENT_BOARD_NAME)
    with open(sp, "w", encoding="utf-8") as f:
        f.write(_summary_block_text(result_entry, 0))
    with open(bp, "w", encoding="utf-8") as f:
        f.write(_board_block_text(result_entry, 0))
    mls = result_entry.get("move_lines") or []
    if moves_path and mls:
        mp = os.path.join(game_dir, FRAGMENT_MOVES_NAME)
        with open(mp, "w", encoding="utf-8") as f:
            f.write("\n".join(mls) + "\n")


def maybe_periodic_export_benchmark_merged(
    benchmark_setup: dict,
    summary_path: str,
    board_path: str,
    moves_path: str | None,
    benchmark_state: dict,
) -> None:
    """Sau mỗi export_merged_every_n_games ván (đếm số ván có fragment), gộp fragments → master."""
    n = int(benchmark_setup.get("export_merged_every_n_games", 0) or 0)
    if n <= 0:
        return
    frag = benchmark_state.get("_fragments_dir") or os.path.join(
        os.path.dirname(summary_path), "fragments"
    )
    frag_count = count_fragment_games(frag)
    if frag_count > 0 and frag_count % n == 0:
        export_benchmark_merged_reports(
            summary_path, board_path, moves_path, frag
        )


def _rewrite_benchmark_result_files(
    summary_path: str,
    board_path: str,
    moves_path: str | None,
    benchmark_state: dict,
) -> None:
    """Tương thích: gộp fragments → master (không dùng benchmark_state['results'])."""
    frag = benchmark_state.get("_fragments_dir") or os.path.join(
        os.path.dirname(summary_path), "fragments"
    )
    export_benchmark_merged_reports(summary_path, board_path, moves_path, frag)


def write_benchmark_reports(
    benchmark_state: dict, summary_path: str, board_path: str, moves_path: str | None = None
) -> None:
    with _append_lock:
        _rewrite_benchmark_result_files(
            summary_path, board_path, moves_path, benchmark_state
        )


def reset_benchmark_report_files(
    summary_path: str,
    board_path: str,
    moves_path: str | None = None,
    fragments_dir: str | None = None,
) -> None:
    paths = [summary_path, board_path]
    if moves_path:
        paths.append(moves_path)
    _ensure_benchmark_result_dirs(*paths)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("")
    with open(board_path, "w", encoding="utf-8") as f:
        f.write("")
    if moves_path:
        with open(moves_path, "w", encoding="utf-8") as f:
            f.write("")
    fd = fragments_dir or os.path.join(os.path.dirname(summary_path), "fragments")
    os.makedirs(fd, exist_ok=True)
    if os.path.isdir(fd):
        for fn in os.listdir(fd):
            path = os.path.join(fd, fn)
            if os.path.isfile(path) and fn.startswith(("summary_", "board_", "moves_")) and fn.endswith(
                ".txt"
            ):
                try:
                    os.remove(path)
                except OSError:
                    pass
            elif os.path.isdir(path) and os.path.isfile(
                os.path.join(path, FRAGMENT_SUMMARY_NAME)
            ):
                try:
                    shutil.rmtree(path)
                except OSError:
                    pass
    msg = f"{summary_path}, {board_path}"
    if moves_path:
        msg += f", {moves_path}"
    msg += f", fragments={fd}"
    print(f"[BENCH] reset report files: {msg}")


def benchmark_record_move(
    benchmark_state: dict,
    agent_key: str,
    elapsed: float | None,
    current: dict | None = None,
    *,
    row: int | None = None,
    col: int | None = None,
    piece: str | None = None,
) -> None:
    if elapsed is None:
        return
    cur = current if current is not None else benchmark_state.get("current")
    if cur is None:
        return
    st = cur["stats"][agent_key]
    st["move_time_total"] += elapsed
    st["move_count"] += 1
    st.setdefault("move_times", []).append(float(elapsed))

    if row is None or col is None or piece is None:
        return
    mid = f"{cur['matchup_name']}__game_{cur['game_idx'] + 1}"
    cur.setdefault("move_log_lines", [])
    if not cur["move_log_lines"]:
        cur["move_log_lines"].append(f"game_seq={cur.get('game_seq', 0)}")
        cur["move_log_lines"].append(f"match_id={mid}")
    cur["move_log_lines"].append(
        f"actor={agent_key}; piece={piece}; elapsed={elapsed:.3f}s; coord=({row},{col})"
    )
