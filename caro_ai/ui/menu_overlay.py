"""Top-menu and modal UI helpers for app.py."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pygame

WHITE = (255, 255, 255)


def default_desktop_dir() -> str:
    home = Path.home()
    desktop = home / "Desktop"
    return str(desktop if desktop.exists() else home)


def browse_json_file(initial_dir: str) -> str | None:
    """Open native file dialog; avoid tkinter freeze on Linux pygame sessions."""
    try:
        if sys.platform.startswith("linux"):
            env = os.environ.copy()
            # Through remote desktop (e.g. RustDesk), forcing portal often improves pointer focus.
            env.setdefault("GTK_USE_PORTAL", "1")
            if shutil.which("zenity"):
                res = subprocess.run(
                    [
                        "zenity",
                        "--file-selection",
                        "--modal",
                        "--title=Choose benchmark config JSON",
                        "--filename",
                        os.path.join(initial_dir, ""),
                        "--file-filter=*.json",
                        "--file-filter=*",
                    ],
                    capture_output=True,
                    text=True,
                    env=env,
                    check=False,
                )
                picked = res.stdout.strip()
                return picked or None
            if shutil.which("kdialog"):
                res = subprocess.run(
                    ["kdialog", "--getopenfilename", initial_dir, "*.json"],
                    capture_output=True,
                    text=True,
                    env=env,
                    check=False,
                )
                picked = res.stdout.strip()
                return picked or None
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askopenfilename(
            title="Choose benchmark config JSON",
            initialdir=initial_dir,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        root.destroy()
        return selected or None
    except Exception:
        return None


def draw_text_button(
    surface,
    rect: pygame.Rect,
    label: str,
    *,
    enabled: bool = True,
    selected: bool = False,
) -> None:
    if not enabled:
        bg = (70, 70, 70)
    elif selected:
        bg = (55, 110, 190)
    else:
        bg = (38, 38, 38)
    pygame.draw.rect(surface, bg, rect, border_radius=6)
    pygame.draw.rect(surface, (170, 170, 170), rect, 1, border_radius=6)
    font = pygame.font.Font("freesansbold.ttf", 16)
    text = font.render(label, True, WHITE)
    surface.blit(text, text.get_rect(center=rect.center))


def top_menu_rects() -> tuple[pygame.Rect, list[str], list[pygame.Rect]]:
    menu_x = 8
    menu_w = 140
    menu_h = 28
    menu_y = 4
    menu_button_rect = pygame.Rect(menu_x, menu_y, menu_w, menu_h)
    menu_items = ["Help", "About", "NormalMode", "CustomAI", "DevMode", "BenchMarkMode"]
    menu_item_rects = [
        pygame.Rect(menu_x, menu_button_rect.bottom + i * menu_h, menu_w + 80, menu_h)
        for i in range(len(menu_items))
    ]
    return menu_button_rect, menu_items, menu_item_rects
