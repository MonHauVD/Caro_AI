"""Bố cục UI: mode thường / dev (bàn + panel) và thanh điều khiển benchmark đa bàn."""

from __future__ import annotations

from typing import Any

import pygame

from caro_ai.benchmark import multi as bench_multi
from caro_ai.modes import GameMode
from caro_ai.ui import buttons as button

# Khoảng trống phía trên lưới bàn: nút global (~y=8, cao ~52) + dòng tiến độ (font ~18) + lề.
BENCH_PROGRESS_LINE_Y = 72
BENCH_MULTI_TOP = 118


def set_button_position(btn: button.Button, x: int, y: int) -> None:
    btn.x = x
    btn.y = y
    btn.rect.topleft = (x, y)


def set_button_scale(btn: button.Button, normal_img, gray_img, scale: float) -> None:
    btn.image = pygame.transform.smoothscale(
        normal_img,
        (max(20, int(normal_img.get_width() * scale)), max(20, int(normal_img.get_height() * scale))),
    )
    btn.gray_image = pygame.transform.smoothscale(
        gray_img,
        (max(20, int(gray_img.get_width() * scale)), max(20, int(gray_img.get_height() * scale))),
    )
    btn.rect = btn.image.get_rect(topleft=(btn.x, btn.y))


def layout_normal_dev_panel(
    new_width: int,
    new_height: int,
    *,
    colnum: int,
    rownum: int,
    x_img_org: pygame.Surface,
    o_img_org: pygame.Surface,
    start_button,
    pause_button,
    replay_button,
    exit_button,
    undo_button,
    ai_btn,
    person_btn,
    h_btn,
    m_btn,
    e_btn,
    ai_thinking_btn,
    pvp_btn,
    aivp_btn,
    logo_btn,
    start_img_org,
    pause_img_org,
    replay_img_org,
    exit_img_org,
    undo_img_org,
    ai_img_org,
    person_img_org,
    ai_img_gray_org,
    person_img_gray_org,
    h_img_org,
    h_img_gray_org,
    m_img_org,
    m_img_gray_org,
    e_img_org,
    e_img_gray_org,
    pvp_img_org,
    pvp_img_gray_org,
    aivp_img_org,
    aivp_img_gray_org,
    ai_thinking_img_org,
    ai_thinking_img_gray_org,
    logo_img_org,
) -> dict[str, Any]:
    """Tính kích thước bàn, panel và vị trí nút cho Normal / Dev (một bàn)."""
    new_width = max(980, int(new_width))
    new_height = max(640, int(new_height))

    panel_width = max(320, int(new_width * 0.28))
    board_available_w = max(200, new_width - panel_width - 30)
    board_available_h = max(200, new_height - 20)
    cell_total = max(8, int(min(board_available_w / colnum, board_available_h / rownum)))
    margin = max(1, cell_total // 15)
    width = max(6, cell_total - margin)
    height = width

    board_pixel_w = colnum * (width + margin) + margin
    board_pixel_h = rownum * (height + margin) + margin
    board_offset_x = max(5, int((board_available_w - board_pixel_w) / 2))
    board_offset_y = max(5, int((new_height - board_pixel_h) / 2))
    panel_x = int(board_offset_x + board_pixel_w + 20)

    x_img = pygame.transform.smoothscale(x_img_org, (max(6, int(width)), max(6, int(height))))
    o_img = pygame.transform.smoothscale(o_img_org, (max(6, int(width)), max(6, int(height))))

    ui_scale = max(0.5, min(1.0, min(new_width / 1280, new_height / 720)))
    start_scale = max(0.75, 0.8 * ui_scale)
    set_button_scale(start_button, start_img_org, start_img_org, start_scale)
    set_button_scale(pause_button, pause_img_org, pause_img_org, start_scale)
    set_button_scale(replay_button, replay_img_org, replay_img_org, 0.8 * ui_scale)
    set_button_scale(exit_button, exit_img_org, exit_img_org, 0.8 * ui_scale)
    set_button_scale(undo_button, undo_img_org, undo_img_org, 0.8 * ui_scale)
    set_button_scale(ai_btn, ai_img_org, ai_img_gray_org, 0.8 * ui_scale)
    set_button_scale(person_btn, person_img_org, person_img_gray_org, 0.8 * ui_scale)
    set_button_scale(h_btn, h_img_org, h_img_gray_org, 0.8 * ui_scale)
    set_button_scale(m_btn, m_img_org, m_img_gray_org, 0.8 * ui_scale)
    set_button_scale(e_btn, e_img_org, e_img_gray_org, 0.8 * ui_scale)
    set_button_scale(ai_thinking_btn, ai_thinking_img_org, ai_thinking_img_gray_org, 0.8 * ui_scale)
    set_button_scale(pvp_btn, pvp_img_org, pvp_img_gray_org, 0.8 * ui_scale)
    set_button_scale(aivp_btn, aivp_img_org, aivp_img_gray_org, 0.8 * ui_scale)
    set_button_scale(logo_btn, logo_img_org, logo_img_org, 0.6 * ui_scale)

    set_button_position(replay_button, panel_x + 30, new_height - 145)
    set_button_position(exit_button, panel_x + 30, new_height - 235)
    set_button_position(undo_button, panel_x + 30, new_height - 325)
    pause_x = undo_button.rect.x
    pause_y = max(40, undo_button.rect.y - pause_button.rect.height - 12)
    start_x = undo_button.rect.x
    start_y = max(40, pause_y - start_button.rect.height - 12)
    set_button_position(start_button, start_x, start_y)
    set_button_position(pause_button, pause_x, pause_y)
    set_button_position(ai_btn, panel_x + 30, 305)
    set_button_position(person_btn, panel_x + 135, 305)
    set_button_position(h_btn, panel_x + 160, 235)
    set_button_position(m_btn, panel_x + 95, 235)
    set_button_position(e_btn, panel_x + 30, 235)
    set_button_position(ai_thinking_btn, panel_x + 80, 30)
    set_button_position(pvp_btn, panel_x + 135, 145)
    set_button_position(aivp_btn, panel_x + 30, 145)
    set_button_position(logo_btn, panel_x + 50, new_height - 55)

    return {
        "window_size": [new_width, new_height],
        "margin": margin,
        "width": width,
        "height": height,
        "board_offset_x": board_offset_x,
        "board_offset_y": board_offset_y,
        "panel_x": panel_x,
        "x_img": x_img,
        "o_img": o_img,
    }


def layout_benchmark_multi_global(
    window_w: int,
    window_h: int,
    *,
    benchmark_state: dict,
    start_button,
    pause_button,
    replay_button,
    exit_button,
    start_img,
    pause_img,
    replay_img,
    start_img_org,
    pause_img_org,
    replay_img_org,
    x_img_org,
    o_img_org,
) -> None:
    set_button_position(start_button, 12, 8)
    set_button_position(pause_button, start_button.rect.right + 10, 8)
    set_button_position(replay_button, pause_button.rect.right + 10, 8)
    set_button_position(exit_button, max(120, window_w - exit_button.rect.width - 12), 8)
    slots = benchmark_state["slots"]
    bench_multi.layout_slots_grid(
        slots,
        window_w,
        window_h,
        BENCH_MULTI_TOP,
        start_img=start_img,
        pause_img=pause_img,
        replay_img=replay_img,
        start_img_org=start_img_org,
        pause_img_org=pause_img_org,
        replay_img_org=replay_img_org,
        x_img_org=x_img_org,
        o_img_org=o_img_org,
        set_button_scale=set_button_scale,
        set_button_position=set_button_position,
        btn_scale=0.22,
    )


def update_window_layout(
    new_width: int,
    new_height: int,
    *,
    game_mode: GameMode,
    benchmark_state: dict,
    colnum: int,
    rownum: int,
    window_size_mut: list,
    layout_globals: dict,
    normal_assets: dict,
    benchmark_bar_assets: dict,
) -> None:
    """Điều phối layout theo mode; ghi kết quả vào layout_globals (margin, width, …)."""
    new_width = max(980, int(new_width))
    new_height = max(640, int(new_height))
    if (
        game_mode is GameMode.BENCHMARK
        and benchmark_state.get("initialized")
        and benchmark_state.get("parallel_workers", 1) > 1
    ):
        window_size_mut[0] = new_width
        window_size_mut[1] = new_height
        layout_benchmark_multi_global(
            new_width,
            new_height,
            benchmark_state=benchmark_state,
            **benchmark_bar_assets,
        )
        return

    d = layout_normal_dev_panel(
        new_width,
        new_height,
        colnum=colnum,
        rownum=rownum,
        **normal_assets,
    )
    window_size_mut[0] = d["window_size"][0]
    window_size_mut[1] = d["window_size"][1]
    layout_globals["MARGIN"] = d["margin"]
    layout_globals["WIDTH"] = d["width"]
    layout_globals["HEIGHT"] = d["height"]
    layout_globals["BOARD_OFFSET_X"] = d["board_offset_x"]
    layout_globals["BOARD_OFFSET_Y"] = d["board_offset_y"]
    layout_globals["PANEL_X"] = d["panel_x"]
    layout_globals["x_img"] = d["x_img"]
    layout_globals["o_img"] = d["o_img"]
