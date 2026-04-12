"""Hỗ trợ benchmark nhiều bàn trong một cửa sổ: hàng đợi trận chung, không trùng lặp."""

from __future__ import annotations

import copy
import math
import time
from typing import Any, Callable

import pygame

from caro_ai.ai.agent import Agent
import caro_ai.game.caro as caro
from caro_ai.ui import buttons as button


def new_agent_stats() -> dict[str, Any]:
    return {
        'wins': 0,
        'losses': 0,
        'draws': 0,
        'move_time_total': 0.0,
        'move_count': 0,
        'move_times': [],
    }


def make_matchup_setup(
    matchup: dict,
    game_idx: int,
    game: caro.Caro,
) -> tuple[Agent, Agent, dict[str, Any]]:
    swap = (game_idx % 2 == 1)
    a = matchup['agent_a']
    b = matchup['agent_b']
    x_side = b if swap else a
    o_side = a if swap else b
    game.reset()
    game.use_ai(True)
    game.set_ai_turn(2)
    cx = copy.deepcopy(x_side.get('config', {}) or {})
    co = copy.deepcopy(o_side.get('config', {}) or {})
    agent_x = Agent(max_depth=x_side['depth'], XO='X', config=cx, log_init=False)
    agent_o = Agent(max_depth=o_side['depth'], XO='O', config=co, log_init=False)
    current: dict[str, Any] = {
        'matchup_name': matchup['name'],
        'game_idx': game_idx,
        'swap': swap,
        'x_label': x_side['label'],
        'o_label': o_side['label'],
        'x_config': {'depth': x_side['depth'], **cx},
        'o_config': {'depth': o_side['depth'], **co},
        'stats': {
            x_side['label']: new_agent_stats(),
            o_side['label']: new_agent_stats(),
        },
    }
    return agent_x, agent_o, current


def create_slot(
    slot_id: int,
    rows: int,
    cols: int,
    winning_condition: int,
    origin_xo: str,
) -> dict[str, Any]:
    return {
        'id': slot_id,
        'game': caro.Caro(rows, cols, winning_condition, origin_xo),
        'agent1': None,
        'agent2': None,
        'current': None,
        'status': -1,
        'turn_started_at': None,
        'turn_elapsed_snapshot': 0.0,
        'dev_future': None,
        'running': False,
        'paused': True,
        'game_ended_at': None,
        'end_finalize_done': False,
        'title': f'Bàn {slot_id + 1}',
        'matchup_idx': 0,
        'game_idx': 0,
        'rect_outer': pygame.Rect(0, 0, 1, 1),
        'board_rect': pygame.Rect(0, 0, 1, 1),
        'bw': 10.0,
        'bh': 10.0,
        'bm': 2.0,
        'box': 0,
        'boy': 0,
        'x_img': None,
        'o_img': None,
        'btn_start': None,
        'btn_pause': None,
        'btn_replay': None,
    }


def layout_slots_grid(
    slots: list[dict[str, Any]],
    window_w: int,
    window_h: int,
    top_bar: int,
    *,
    start_img,
    pause_img,
    replay_img,
    start_img_org,
    pause_img_org,
    replay_img_org,
    x_img_org,
    o_img_org,
    set_button_scale: Callable,
    set_button_position: Callable,
    btn_scale: float = 0.2,
) -> None:
    n = len(slots)
    if n == 0:
        return
    cols = max(1, int(math.ceil(math.sqrt(n))))
    rows = max(1, int(math.ceil(n / cols)))
    aw = max(120, window_w - 16)
    ah = max(120, window_h - top_bar - 12)
    cw = aw // cols
    ch = ah // rows
    for i, slot in enumerate(slots):
        r, c = divmod(i, cols)
        ox = 8 + c * cw
        oy = top_bar + 4 + r * ch
        outer = pygame.Rect(ox, oy, cw - 4, ch - 4)
        slot['rect_outer'] = outer
        title_h = 44  # hai dòng tiêu đề (tên ván + game_seq/total căn phải)
        ctrl_h = 36
        board_top = outer.y + title_h + ctrl_h + 4
        board_h = max(80, outer.bottom - board_top - 6)
        board_w = max(80, outer.width - 8)
        slot['board_rect'] = pygame.Rect(outer.x + 4, board_top, board_w, board_h)
        g = slot['game']
        cn, rn = g.cols, g.rows
        cell = min((board_w - 4) / cn, (board_h - 4) / rn)
        slot['bm'] = max(1.0, cell / 15)
        slot['bw'] = max(4.0, cell - slot['bm'])
        slot['bh'] = slot['bw']
        slot['box'] = slot['board_rect'].x + max(2, (board_w - cn * (slot['bw'] + slot['bm']) - slot['bm']) / 2)
        slot['boy'] = slot['board_rect'].y + max(2, (board_h - rn * (slot['bh'] + slot['bm']) - slot['bm']) / 2)
        iw = max(4, int(slot['bw']))
        slot['x_img'] = pygame.transform.smoothscale(x_img_org, (iw, iw))
        slot['o_img'] = pygame.transform.smoothscale(o_img_org, (iw, iw))
        bx = outer.x + 6
        by = outer.y + title_h + 2
        if slot['btn_start'] is None:
            slot['btn_start'] = button.Button(bx, by, start_img, start_img, btn_scale)
            slot['btn_pause'] = button.Button(bx + 50, by, pause_img, pause_img, btn_scale)
            slot['btn_replay'] = button.Button(bx + 100, by, replay_img, replay_img, btn_scale)
        else:
            set_button_scale(slot['btn_start'], start_img_org, start_img_org, btn_scale)
            set_button_scale(slot['btn_pause'], pause_img_org, pause_img_org, btn_scale)
            set_button_scale(slot['btn_replay'], replay_img_org, replay_img_org, btn_scale)
            set_button_position(slot['btn_start'], bx, by)
            set_button_position(slot['btn_pause'], bx + 52, by)
            set_button_position(slot['btn_replay'], bx + 104, by)


def draw_slot_board(slot: dict[str, Any], surface: pygame.Surface, *, white, green) -> None:
    g = slot['game']
    bw, bh, bm = slot['bw'], slot['bh'], slot['bm']
    box, boy = slot['box'], slot['boy']
    for row in range(g.rows):
        for col in range(g.cols):
            color = white
            if g.last_move:
                lr, lc = g.last_move[-1][0], g.last_move[-1][1]
                if row == lr and col == lc:
                    color = green
            pygame.draw.rect(
                surface,
                color,
                [
                    int(box + (bm + bw) * col + bm),
                    int(boy + (bm + bh) * row + bm),
                    int(bw),
                    int(bh),
                ],
            )
            ch = g.grid[row][col]
            if ch == 'X':
                surface.blit(
                    slot['x_img'],
                    (int(box + (bw + bm) * col + bm), int(boy + (bh + bm) * row + bm)),
                )
            elif ch == 'O':
                surface.blit(
                    slot['o_img'],
                    (int(box + (bw + bm) * col + bm), int(boy + (bh + bm) * row + bm)),
                )


def apply_move_slot(
    slot: dict[str, Any], row: int, col: int, actor: str, *, log: bool = True
) -> tuple[float | None, str | None]:
    g = slot['game']
    before_len = len(g.last_move)
    moved_piece = g.XO
    t0 = slot['turn_started_at']
    elapsed = (time.perf_counter() - t0) if t0 is not None else 0.0
    g.make_move(row, col)
    if len(g.last_move) > before_len:
        slot['turn_started_at'] = None
        if log:
            print(
                f"[BENCH][bàn {slot['id'] + 1}] actor={actor}; piece={moved_piece}; "
                f"elapsed={elapsed:.3f}s; coord=({row},{col})"
            )
        return elapsed, moved_piece
    return None, None
