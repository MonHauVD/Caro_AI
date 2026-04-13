"""Gộp fragment benchmark → file master; chỉ dùng stdlib (không pygame)."""

from __future__ import annotations

import glob
import json
import os
import re

# Mỗi ván: fragments/<{game_seq:08d}_{match_id_slug}>/{summary,board,moves}.txt
FRAGMENT_SUMMARY_NAME = "summary.txt"
FRAGMENT_BOARD_NAME = "board.txt"
FRAGMENT_MOVES_NAME = "moves.txt"

_FS_BAD = frozenset('<>:"/\\|?*\x00')
_LEGACY_SUMMARY_RE = re.compile(r"^summary_(\d+)\.txt$")


def sanitize_match_id_for_fs(match_id: str, max_slug_len: int = 150) -> str:
    """Tên thư mục an toàn cho Windows / Unix; giữ chữ số, chữ, _, -, ."""
    out: list[str] = []
    for ch in match_id:
        if ord(ch) < 32 or ch in _FS_BAD:
            out.append("_")
        else:
            out.append(ch)
    s = "".join(out).strip(" .") or "match"
    if len(s) > max_slug_len:
        s = s[:max_slug_len].rstrip(" .") or "match"
    return s


def fragment_subdirectory_name(game_seq: int, match_id: str) -> str:
    """Tiền tố 8 chữ số để sắp xếp alphabet = thứ tự game_seq."""
    slug = sanitize_match_id_for_fs(match_id)
    return f"{int(game_seq):08d}_{slug}"


def _game_seq_from_subdir_name(dirname: str) -> int | None:
    if len(dirname) < 9 or dirname[8] != "_":
        return None
    head = dirname[:8]
    if not head.isdigit():
        return None
    return int(head)


def _read_game_seq_from_summary(path: str) -> int | None:
    try:
        with open(path, encoding="utf-8") as f:
            for _ in range(20):
                line = f.readline()
                if not line:
                    break
                line = line.strip()
                if line.startswith("game_seq="):
                    return int(line.split("=", 1)[1].strip())
    except (OSError, ValueError):
        return None
    return None


def collect_fragment_games_sorted(
    fragments_dir: str,
) -> list[tuple[int, str, str, str | None]]:
    """
    Trả về danh sách (game_seq, summary_path, board_path, moves_path) đã sắp theo game_seq.
    Hỗ trợ layout cũ (summary_NNNNNN.txt ở root) và layout mới (mỗi ván một thư mục con).
    """
    if not fragments_dir or not os.path.isdir(fragments_dir):
        return []

    by_seq: dict[int, tuple[int, str, str, str | None]] = {}

    # Legacy: fragments/summary_000042.txt
    for sp in glob.glob(os.path.join(fragments_dir, "summary_*.txt")):
        base = os.path.basename(sp)
        m = _LEGACY_SUMMARY_RE.match(base)
        if not m:
            continue
        seq = int(m.group(1))
        frag = fragments_dir
        bp = os.path.join(frag, f"board_{seq:06d}.txt")
        mp = os.path.join(frag, f"moves_{seq:06d}.txt")
        moves_path = mp if os.path.isfile(mp) else None
        board_path = bp if os.path.isfile(bp) else ""
        by_seq[seq] = (seq, sp, board_path, moves_path)

    # Mới: fragments/00000042_match__game_1/summary.txt
    try:
        for entry in os.scandir(fragments_dir):
            if not entry.is_dir():
                continue
            sub = entry.path
            sp = os.path.join(sub, FRAGMENT_SUMMARY_NAME)
            if not os.path.isfile(sp):
                continue
            seq = _game_seq_from_subdir_name(entry.name)
            if seq is None:
                seq = _read_game_seq_from_summary(sp)
            if seq is None:
                continue
            bp = os.path.join(sub, FRAGMENT_BOARD_NAME)
            mp = os.path.join(sub, FRAGMENT_MOVES_NAME)
            board_path = bp if os.path.isfile(bp) else ""
            moves_path = mp if os.path.isfile(mp) else None
            by_seq[seq] = (seq, sp, board_path, moves_path)
    except OSError:
        pass

    return [by_seq[k] for k in sorted(by_seq.keys())]


def list_fragment_summary_paths_in_order(fragments_dir: str) -> list[str]:
    return [t[1] for t in collect_fragment_games_sorted(fragments_dir)]


def count_fragment_games(fragments_dir: str) -> int:
    return len(collect_fragment_games_sorted(fragments_dir))


def _ensure_benchmark_result_dirs(*paths: str) -> None:
    for p in paths:
        if not p:
            continue
        d = os.path.dirname(p)
        if d:
            os.makedirs(d, exist_ok=True)


def _patch_export_completion_block(block_text: str, completion_index: int) -> str:
    """Fragment ghi completion_index=0; khi export master chỉnh lại dòng đầu + JSON stats."""
    lines = block_text.strip().split("\n")
    out: list[str] = []
    for line in lines:
        if line.startswith("completion_index="):
            out.append(f"completion_index={completion_index}")
        elif line.startswith("stats="):
            try:
                obj = json.loads(line[6:])
                obj["completion_index"] = completion_index
                out.append("stats=" + json.dumps(obj, ensure_ascii=False))
            except json.JSONDecodeError:
                out.append(line)
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def export_benchmark_merged_reports(
    summary_path: str,
    board_path: str,
    moves_path: str | None,
    fragments_dir: str,
) -> None:
    """
    Gộp fragments theo game_seq → file master (đọc từng file nhỏ tuần tự, không giữ cả cỡ lớn trong RAM).
    Gọi khi kết thúc phiên benchmark hoặc khi cần bản tổng hợp cập nhật.
    """
    games = collect_fragment_games_sorted(fragments_dir)
    _ensure_benchmark_result_dirs(summary_path, board_path, moves_path or "")

    parts_s: list[str] = []
    parts_b: list[str] = []
    parts_m: list[str] = []
    for i, (_seq, sp, bp, mp) in enumerate(games):
        ci = i + 1
        try:
            with open(sp, encoding="utf-8") as f:
                parts_s.append(_patch_export_completion_block(f.read(), ci))
        except OSError:
            continue
        if bp and os.path.isfile(bp):
            try:
                with open(bp, encoding="utf-8") as f:
                    parts_b.append(_patch_export_completion_block(f.read(), ci))
            except OSError:
                pass
        if moves_path and mp and os.path.isfile(mp):
            try:
                with open(mp, encoding="utf-8") as f:
                    parts_m.append(f.read().strip())
            except OSError:
                pass

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(s.strip() for s in parts_s).strip() + ("\n" if parts_s else ""))
    with open(board_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(s.strip() for s in parts_b).strip() + ("\n" if parts_b else ""))
    if moves_path:
        mt = "\n\n".join(s for s in parts_m if s).strip()
        with open(moves_path, "w", encoding="utf-8") as f:
            f.write((mt + "\n") if mt else "")

    print(f"[BENCH] exported {len(parts_s)} game(s) from fragments -> {summary_path}")


def export_benchmark_fragments_if_any(
    summary_path: str,
    board_path: str,
    moves_path: str | None,
    fragments_dir: str,
) -> bool:
    """Nếu có fragment summary thì gộp ra 3 file master; không thì bỏ qua. Trả về True nếu đã export."""
    if not collect_fragment_games_sorted(fragments_dir):
        return False
    export_benchmark_merged_reports(
        summary_path, board_path, moves_path, fragments_dir
    )
    return True
