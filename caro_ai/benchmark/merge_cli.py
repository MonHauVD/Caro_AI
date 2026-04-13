"""CLI gộp fragments → master; không import pygame (dùng từ python -m caro_ai --bench-export-merge)."""

from __future__ import annotations

import argparse
import json
import os
import sys

from caro_ai.app_helpers import resolve_config_dir
from caro_ai.benchmark.report_merge import export_benchmark_fragments_if_any

_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.abspath(os.path.join(_PKG_DIR, ".."))


def _default_benchmark_config_path() -> str:
    return os.path.join(resolve_config_dir(_PROJECT_ROOT), "benchmark_config.json")


def _output_dir_from_benchmark_json(path: str) -> str | None:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    od = data.get("output_dir")
    if isinstance(od, str) and od.strip():
        return od.strip()
    return None


def resolve_benchmark_results_dir(
    *,
    benchmark_config: str | None,
    bench_results_dir: str | None,
) -> str:
    if bench_results_dir:
        return os.path.abspath(bench_results_dir)
    cfg = benchmark_config if benchmark_config is not None else _default_benchmark_config_path()
    cfg = os.path.abspath(cfg)
    od = _output_dir_from_benchmark_json(cfg) or "benchmarks/results"
    return od if os.path.isabs(od) else os.path.join(_PROJECT_ROOT, od)


def run_export_merge(
    *,
    benchmark_config: str | None,
    bench_results_dir: str | None,
) -> bool:
    rd = resolve_benchmark_results_dir(
        benchmark_config=benchmark_config,
        bench_results_dir=bench_results_dir,
    )
    sp = os.path.join(rd, "benchmark_results_summary.txt")
    bp = os.path.join(rd, "benchmark_results_boards.txt")
    mp = os.path.join(rd, "benchmark_results_moves.txt")
    frag = os.path.join(rd, "fragments")
    return export_benchmark_fragments_if_any(sp, bp, mp, frag)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Gộp benchmarks/.../fragments → 3 file benchmark_results_*.txt (không cần pygame)."
    )
    p.add_argument(
        "--benchmark-config",
        metavar="PATH",
        default=None,
        help="File benchmark JSON để đọc output_dir (mặc định: config/benchmark_config.json dưới project).",
    )
    p.add_argument(
        "--bench-results-dir",
        metavar="DIR",
        default=None,
        help="Thư mục chứa benchmark_results_*.txt và fragments/ (ghi đè output_dir trong JSON).",
    )
    ns = p.parse_args(argv)
    if run_export_merge(
        benchmark_config=ns.benchmark_config,
        bench_results_dir=ns.bench_results_dir,
    ):
        rd = resolve_benchmark_results_dir(
            benchmark_config=ns.benchmark_config,
            bench_results_dir=ns.bench_results_dir,
        )
        print(f"[BENCH] đã gộp fragments → master trong {rd}")
        return 0
    rd = resolve_benchmark_results_dir(
        benchmark_config=ns.benchmark_config,
        bench_results_dir=ns.bench_results_dir,
    )
    print(
        f"[BENCH] không có fragment ván nào trong {os.path.join(rd, 'fragments')}",
        file=sys.stderr,
    )
    return 0

