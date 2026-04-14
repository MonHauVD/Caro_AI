"""Helpers for Custom AI mode UI and config fields."""

from __future__ import annotations

import pygame


def cfg_to_fields(cfg: dict) -> dict[str, str]:
    return {
        "use_cython_search": str(bool(cfg.get("use_cython_search", False))).lower(),
        "use_tss": str(bool(cfg.get("use_tss", False))).lower(),
        "use_lazy_smp": str(bool(cfg.get("use_lazy_smp", False))).lower(),
        "beam_width_root": str(int(cfg.get("beam_width_root", 0))),
        "beam_width_inner": str(int(cfg.get("beam_width_inner", 0))),
        "move_time_budget_sec": str(int(cfg.get("move_time_budget_sec", 20))),
    }


def fields_to_cfg(fields: dict[str, str]) -> dict:
    return {
        "use_cython_search": fields["use_cython_search"].strip().lower() in ("1", "true", "yes", "y"),
        "use_tss": fields["use_tss"].strip().lower() in ("1", "true", "yes", "y"),
        "use_lazy_smp": fields["use_lazy_smp"].strip().lower() in ("1", "true", "yes", "y"),
        "beam_width_root": int(fields["beam_width_root"].strip() or "0"),
        "beam_width_inner": int(fields["beam_width_inner"].strip() or "0"),
        "move_time_budget_sec": int(fields["move_time_budget_sec"].strip() or "20"),
    }


def draw_custom_ai_summary(
    screen,
    *,
    panel_x: int,
    title_y: int,
    summary: dict,
    white=(255, 255, 255),
    muted=(205, 205, 205),
) -> None:
    title_font = pygame.font.Font("freesansbold.ttf", 22)
    small_font = pygame.font.Font("freesansbold.ttf", 14)
    screen.blit(title_font.render("Custom AI", True, white), (panel_x + 30, title_y))
    cfg = summary.get("config", {})
    fields = [
        ("preset", summary.get("preset_name", "custom")),
        ("depth", str(summary.get("depth", 0))),
        ("cython", str(bool(cfg.get("use_cython_search", False))).lower()),
        ("tss", str(bool(cfg.get("use_tss", False))).lower()),
        ("smp", str(bool(cfg.get("use_lazy_smp", False))).lower()),
        ("beam root", str(cfg.get("beam_width_root", 0))),
        ("beam inner", str(cfg.get("beam_width_inner", 0))),
        ("time(sec)", str(cfg.get("move_time_budget_sec", 0))),
    ]
    col_x = [panel_x + 30, panel_x + 130, panel_x + 230]
    row_y0 = title_y + 30
    for i, (k, v) in enumerate(fields):
        cx = col_x[i % 3]
        cy = row_y0 + (i // 3) * 20
        screen.blit(small_font.render(f"{k}: {v}", True, muted), (cx, cy))
