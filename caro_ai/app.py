"""Giao diện pygame và vòng lặp game Caro AI."""

import argparse
import copy
import json
import multiprocessing
import os
import signal
import sys
import time
from collections import deque
from concurrent.futures import ProcessPoolExecutor

import pygame

from caro_ai import app_helpers
from caro_ai.benchmark import session as bench_sess
from caro_ai.benchmark.worker import compute_ai_move_worker
from caro_ai.ui import custom_ai as custom_ai_ui
from caro_ai.ui import layout as ui_layout
from caro_ai.ui import menu_overlay
from caro_ai.ai.agent import Agent
from caro_ai.modes import GameMode
import caro_ai.game.caro as caro
from caro_ai.ui import buttons as button

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_PKG_DIR, '..'))

# -------------------------Setup----------------------------
# Định nghĩa màu

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (77, 199, 61)
RED = (199, 36, 55)
BLUE = (68, 132, 222)

# Kí hiệu lúc ban đầu
XO = 'X'
FPS = 120
# Số hàng, cột
ROWNUM = 18
COLNUM = 20
# Số dòng thắng
winning_condition = 5

# ---------------------------------------------------------------------------
# Player vs AI — preset độ khó (depth + toàn bộ agent.config).
# Chỉnh trực tiếp tại đây; nút Easy / Medium / Hard sẽ dùng các preset này.
# ---------------------------------------------------------------------------
PLAYER_VS_AI_PRESETS = {
    'easy': {
        'depth': 3,
        'config': {
            'use_cython_search': False,
            'use_tss': False,
            'use_lazy_smp': False,
            'beam_width_root': 0,
            'beam_width_inner': 0,
            'move_time_budget_sec': 20,
        },
    },
    'medium': { # "depth_5"
        'depth': 5,
        'config': {
            'use_cython_search': False,
            'use_tss': False,
            'use_lazy_smp': False,
            'beam_width_root': 0,
            'beam_width_inner': 0,
            'move_time_budget_sec': 20,
        },
    },
    'hard': { # "depth_7_beam_a"
        "depth": 7,
        "config": {
            "use_cython_search": False,
            "use_tss": False,
            "use_lazy_smp": False,
            "beam_width_root": 12,
            "beam_width_inner": 9,
            "move_time_budget_sec": 20
      }
    },
    'grand_master': {  # "depth_8_beam_b_180s_timer"
        "depth": 8,
        "config": {
            "use_cython_search": False,
            "use_tss": False,
            "use_lazy_smp": False,
            "beam_width_root": 16,
            "beam_width_inner": 12,
            "move_time_budget_sec": 180,
        },
    },
}

# Độ khó AI lúc mở app — chỉ chỉnh giá trị tại đây ('easy' | 'medium' | 'hard' | 'grand_master').
INITIAL_AI_DIFFICULTY = 'easy'
normal_mode_difficulty = INITIAL_AI_DIFFICULTY


game_mode = GameMode.NORMAL

CONFIG_DIR = app_helpers.resolve_config_dir(_PROJECT_ROOT)
DEV_MODE_CONFIG_FILE = os.path.join(CONFIG_DIR, 'dev_mode.json')
BENCHMARK_CONFIG_FILE = os.path.join(CONFIG_DIR, 'benchmark_config.json')

_DEFAULT_DEV_MODE_SETUP = {
    'ai_1': 'X',
    'ai_2': 'O',
    'ai_1_depth': 6,
    'ai_2_depth': 8,
    'ai_1_config': {
        'use_cython_search': False,
        'use_tss': False,
        'use_lazy_smp': False,
        'move_time_budget_sec': 8,
        'beam_width_root': 0,
        'beam_width_inner': 0,
    },
    'ai_2_config': {
        'use_cython_search': False,
        'use_tss': False,
        'use_lazy_smp': False,
        'move_time_budget_sec': 8,
        'beam_width_root': 0,
        'beam_width_inner': 0,
    },
    'start': False,
    'pause': False,
}

dev_mode_setup: dict = copy.deepcopy(_DEFAULT_DEV_MODE_SETUP)

benchmark_setup = {
    'games_per_matchup': 4,  # Auto-swap first move by alternating X/O each game.
    'output_dir': 'benchmarks/results',
    # 0 = chỉ gộp master khi hết phiên / thoát / CLI; N>0 = gộp sau mỗi N ván đã ghi fragment.
    'export_merged_every_n_games': 4,
    'matchups': [
        {
            'name': 'depth6_vs_depth8_plain',
            'agent_a': {
                'label': 'agent_a',
                'depth': 6,
                'config': {
                    'use_cython_search': False,
                    'use_tss': False,
                    'use_lazy_smp': False,
                    'beam_width_root': 0,
                    'beam_width_inner': 0,
                    'move_time_budget_sec': 12,
                },
            },
            'agent_b': {
                'label': 'agent_b',
                'depth': 8,
                'config': {
                    'use_cython_search': False,
                    'use_tss': False,
                    'use_lazy_smp': False,
                    'beam_width_root': 0,
                    'beam_width_inner': 0,
                    'move_time_budget_sec': 12,
                },
            },
        }
    ],
}

BENCHMARK_RESULT_SUMMARY_FILE = os.path.join(
    _PROJECT_ROOT, 'benchmarks', 'results', 'benchmark_results_summary.txt')
BENCHMARK_RESULT_BOARD_FILE = os.path.join(
    _PROJECT_ROOT, 'benchmarks', 'results', 'benchmark_results_boards.txt')
BENCHMARK_RESULT_MOVES_FILE = os.path.join(
    _PROJECT_ROOT, 'benchmarks', 'results', 'benchmark_results_moves.txt')
BENCHMARK_FRAGMENTS_DIR = os.path.join(
    _PROJECT_ROOT, 'benchmarks', 'results', 'fragments')

bench_rt = None


def _ensure_benchmark_result_dirs():
    for p in (
        BENCHMARK_RESULT_SUMMARY_FILE,
        BENCHMARK_RESULT_BOARD_FILE,
        BENCHMARK_RESULT_MOVES_FILE,
    ):
        d = os.path.dirname(p)
        if d:
            os.makedirs(d, exist_ok=True)
    os.makedirs(BENCHMARK_FRAGMENTS_DIR, exist_ok=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Caro AI (pygame + minimax agent).')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        '--dev',
        action='store_true',
        help='AI vs AI; loads dev JSON (--dev-config, default: config/dev_mode.json).',
    )
    mode.add_argument(
        '--benchmark',
        action='store_true',
        help='Automated benchmark; requires benchmark JSON (--benchmark-config, default: config/benchmark_config.json).',
    )
    p.add_argument(
        '--dev-config',
        metavar='PATH',
        default=None,
        help='Path to dev_mode.json (default when using --dev: config/dev_mode.json).',
    )
    p.add_argument(
        '--benchmark-config',
        metavar='PATH',
        default=None,
        help='Path to benchmark config JSON (default with --benchmark: config/benchmark_config.json).',
    )
    p.add_argument(
        '--benchmark-workers',
        type=int,
        default=4,
        metavar='N',
        help=(
            'Chỉ với --benchmark: số bàn cờ hiển thị song song trong một cửa sổ. '
            '1 = một bàn như cũ; >1 = lưới nhiều bàn + Start/Pause chung và riêng. Mặc định: 4.'
        ),
    )
    p.add_argument(
        '--bench-export-merge',
        action='store_true',
        help=(
            'Chỉ gộp thư mục fragments/ → 3 file benchmark_results_*.txt rồi thoát; không mở pygame. '
            'Đường dẫn lấy từ --bench-results-dir hoặc output_dir trong --benchmark-config.'
        ),
    )
    p.add_argument(
        '--bench-results-dir',
        metavar='DIR',
        default=None,
        help=(
            'Với --bench-export-merge: thư mục chứa benchmark_results_summary.txt và fragments/ '
            '(mặc định: output_dir trong file benchmark JSON, hoặc benchmarks/results dưới project).'
        ),
    )
    if argv is None:
        argv = sys.argv[1:]
    return p.parse_args(argv)


def run_benchmark_export_merge_cli(args: argparse.Namespace) -> None:
    """Gộp fragments → 3 file master; dùng khi --bench-export-merge (logic trong merge_cli, không pygame)."""
    from caro_ai.benchmark import merge_cli

    bench_cfg = args.benchmark_config if args.benchmark_config is not None else BENCHMARK_CONFIG_FILE
    if merge_cli.run_export_merge(
        benchmark_config=bench_cfg,
        bench_results_dir=args.bench_results_dir,
    ):
        rd = merge_cli.resolve_benchmark_results_dir(
            benchmark_config=bench_cfg,
            bench_results_dir=args.bench_results_dir,
        )
        print(f"[BENCH] đã gộp fragments → master trong {rd}")
    else:
        rd = merge_cli.resolve_benchmark_results_dir(
            benchmark_config=bench_cfg,
            bench_results_dir=args.bench_results_dir,
        )
        print(
            f"[BENCH] không có summary_*.txt trong {os.path.join(rd, 'fragments')}",
            file=sys.stderr,
        )


def load_dev_mode_config(path: str, *, explicit_file: bool) -> None:
    """Đặt lại dev_mode_setup từ path; nếu không có file: defaults (hoặc thoát nếu explicit_file)."""
    global dev_mode_setup
    dev_mode_setup = copy.deepcopy(_DEFAULT_DEV_MODE_SETUP)
    if not os.path.isfile(path):
        if explicit_file:
            print(f"[DEV] error: file not found: {path}", file=sys.stderr)
            sys.exit(2)
        print(f"[DEV] config not found ({path}), using built-in defaults")
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
    except Exception as ex:
        print(f"[DEV] failed to read {path}: {ex}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(loaded, dict):
        print(f"[DEV] invalid config (expected object): {path}", file=sys.stderr)
        sys.exit(2)
    for k, v in loaded.items():
        if k in ('ai_1_config', 'ai_2_config') and isinstance(v, dict):
            dev_mode_setup[k].update(v)
        else:
            dev_mode_setup[k] = copy.deepcopy(v) if isinstance(v, dict) else v
    print(f"[DEV] loaded config from {path}")


# Cửa sổ pygame chỉ tiến trình chính; worker AI ở caro_ai.benchmark.worker (không import pygame).

START_BTN_ANCHOR_TOP = 120
START_BTN_ANCHOR_RIGHT_MARGIN = 60
SHOW_DEV_START_DEBUG_BORDER = True
TOP_MENU_HEIGHT = 36


def resource_path(relative_path):
    return app_helpers.resource_path(relative_path, _PROJECT_ROOT)


def build_player_vs_ai_agent() -> Agent:
    preset = PLAYER_VS_AI_PRESETS[normal_mode_difficulty]
    cfg = copy.deepcopy(preset['config'])
    return Agent(
        max_depth=preset['depth'],
        XO=my_game.get_current_XO_for_AI(),
        config=cfg,
        log_init=False,
    )


def build_custom_ai_agent(custom_spec: dict) -> Agent:
    return Agent(
        max_depth=int(custom_spec["depth"]),
        XO=my_game.get_current_XO_for_AI(),
        config=copy.deepcopy(custom_spec["config"]),
        log_init=False,
    )


def modal_close_button_rect(panel_rect: pygame.Rect) -> pygame.Rect:
    return pygame.Rect(panel_rect.right - 34, panel_rect.y + 10, 24, 24)


def draw_modal_close_button(surface, panel_rect: pygame.Rect) -> None:
    close_rect = modal_close_button_rect(panel_rect)
    center = close_rect.center
    pygame.draw.circle(surface, (32, 32, 32), center, close_rect.width // 2)
    pygame.draw.circle(surface, (210, 210, 210), center, close_rect.width // 2, 1)
    font = pygame.font.Font("freesansbold.ttf", 18)
    text = font.render("X", True, (235, 70, 70))
    surface.blit(text, text.get_rect(center=center))


def init_application():
    global my_game, agent, agent1, agent2
    global Window_size, BOARD_OFFSET_X, BOARD_OFFSET_Y, PANEL_X, WIDTH, HEIGHT, MARGIN, my_len_min
    global Screen, x_img_org, o_img_org, x_img, o_img
    global start_img_org, pause_img_org, exit_img_org, replay_img_org, undo_img_org
    global ai_img_org, person_img_org, ai_img_gray_org, person_img_gray_org
    global h_img_org, h_img_gray_org, m_img_org, m_img_gray_org, e_img_org, e_img_gray_org
    global gm_img_org, gm_img_gray_org
    global pvp_img_org, pvp_img_gray_org, aivp_img_org, aivp_img_gray_org
    global ai_thinking_img_org, ai_thinking_img_gray_org
    global start_img, pause_img, exit_img, replay_img, undo_img, ai_img, person_img, ai_img_gray, person_img_gray
    global h_img, h_img_gray, m_img, m_img_gray, e_img, e_img_gray, gm_img, gm_img_gray
    global pvp_img, pvp_img_gray, aivp_img, aivp_img_gray, ai_thinking_img, ai_thinking_img_gray
    global icon_img, logo_img_org, logo_img, instructions_img_org
    global start_button, pause_button, replay_button, exit_button, undo_button
    global ai_btn, person_btn, h_btn, m_btn, e_btn, grand_master_btn, ai_thinking_btn, pvp_btn, aivp_btn, logo_btn
    global done, status, clock, turn_started_at, turn_elapsed_frozen, turn_timer_paused, turn_elapsed_paused
    global ai_is_thinking, ai_future, dev_future, ai_executor, benchmark_state, bench_rt

    pygame.init()

    Window_size = [1280, 720]
    BOARD_OFFSET_X = 0
    BOARD_OFFSET_Y = 0
    PANEL_X = 920

    my_len_min = min(900 / COLNUM, (720) / ROWNUM)
    MARGIN = my_len_min / 15
    my_len_min = min((900 - MARGIN) / COLNUM, (720 - MARGIN) / ROWNUM)
    my_len_min = my_len_min - MARGIN
    WIDTH = my_len_min
    HEIGHT = my_len_min

    Screen = pygame.display.set_mode(Window_size, pygame.RESIZABLE)
    asset_path = resource_path('assets')

    x_img_org = pygame.image.load(asset_path + "/X_caro.png").convert_alpha()
    o_img_org = pygame.image.load(asset_path + "/O_caro.png").convert_alpha()
    x_img = pygame.transform.smoothscale(x_img_org, (int(my_len_min), int(my_len_min)))
    o_img = pygame.transform.smoothscale(o_img_org, (int(my_len_min), int(my_len_min)))

    start_img_org = pygame.image.load(asset_path + '/start_btn.png').convert_alpha()
    pause_img_org = pygame.image.load(asset_path + '/pause_btn.png').convert_alpha()
    exit_img_org = pygame.image.load(asset_path + '/exit_btn.png').convert_alpha()
    replay_img_org = pygame.image.load(asset_path + '/replay_btn.png').convert_alpha()
    undo_img_org = pygame.image.load(asset_path + '/undo_btn.png').convert_alpha()
    ai_img_org = pygame.image.load(asset_path + '/ai_btn.png').convert_alpha()
    person_img_org = pygame.image.load(asset_path + '/person_btn.png').convert_alpha()
    ai_img_gray_org = pygame.image.load(asset_path + '/ai_btn_gray.jpg').convert_alpha()
    person_img_gray_org = pygame.image.load(asset_path + '/person_btn_gray.jpg').convert_alpha()
    h_img_org = pygame.image.load(asset_path + '/h_btn.png').convert_alpha()
    h_img_gray_org = pygame.image.load(asset_path + '/h_btn_gray.png').convert_alpha()
    m_img_org = pygame.image.load(asset_path + '/m_btn.png').convert_alpha()
    m_img_gray_org = pygame.image.load(asset_path + '/m_btn_gray.png').convert_alpha()
    e_img_org = pygame.image.load(asset_path + '/e_btn.png').convert_alpha()
    e_img_gray_org = pygame.image.load(asset_path + '/e_btn_gray.png').convert_alpha()
    gm_img_org = pygame.image.load(asset_path + '/gm_btn.png').convert_alpha()
    gm_img_gray_org = pygame.image.load(asset_path + '/gm_btn_gray.png').convert_alpha()
    pvp_img_org = pygame.image.load(asset_path + '/player_vs_player.jpg').convert_alpha()
    pvp_img_gray_org = pygame.image.load(asset_path + '/player_vs_player_gray.jpg').convert_alpha()
    aivp_img_org = pygame.image.load(asset_path + '/ai_vs_player.jpg').convert_alpha()
    aivp_img_gray_org = pygame.image.load(asset_path + '/ai_vs_player_gray.jpg').convert_alpha()
    ai_thinking_img_org = pygame.image.load(asset_path + '/ai_thinking.png').convert_alpha()
    ai_thinking_img_gray_org = pygame.image.load(asset_path + '/ai_thinking_gray.png').convert_alpha()

    start_img = pygame.transform.smoothscale(start_img_org, (240, 105))
    pause_img = pygame.transform.smoothscale(pause_img_org, (240, 105))
    exit_img = pygame.transform.smoothscale(exit_img_org, (240, 105))
    replay_img = pygame.transform.smoothscale(replay_img_org, (240, 105))
    undo_img = pygame.transform.smoothscale(undo_img_org, (240, 105))
    ai_img = pygame.transform.smoothscale(ai_img_org, (105, 105))
    person_img = pygame.transform.smoothscale(person_img_org, (105, 105))
    ai_img_gray = pygame.transform.smoothscale(ai_img_gray_org, (105, 105))
    person_img_gray = pygame.transform.smoothscale(person_img_gray_org, (105, 105))
    h_img = pygame.transform.smoothscale(h_img_org, (80, 80))
    h_img_gray = pygame.transform.smoothscale(h_img_gray_org, (80, 80))
    m_img = pygame.transform.smoothscale(m_img_org, (80, 80))
    m_img_gray = pygame.transform.smoothscale(m_img_gray_org, (80, 80))
    e_img = pygame.transform.smoothscale(e_img_org, (80, 80))
    e_img_gray = pygame.transform.smoothscale(e_img_gray_org, (80, 80))
    gm_img = pygame.transform.smoothscale(gm_img_org, (80, 80))
    gm_img_gray = pygame.transform.smoothscale(gm_img_gray_org, (80, 80))
    pvp_img = pygame.transform.smoothscale(pvp_img_org, (105, 105))
    pvp_img_gray = pygame.transform.smoothscale(pvp_img_gray_org, (105, 105))
    aivp_img = pygame.transform.smoothscale(aivp_img_org, (105, 105))
    aivp_img_gray = pygame.transform.smoothscale(aivp_img_gray_org, (105, 105))
    ai_thinking_img = pygame.transform.smoothscale(ai_thinking_img_org, (105, 105))
    ai_thinking_img_gray = pygame.transform.smoothscale(ai_thinking_img_gray_org, (105, 105))
    icon_img = pygame.transform.smoothscale(
        pygame.image.load(asset_path + '/old/icon.jpg').convert_alpha(), (20, 20))
    logo_img_org = pygame.image.load(asset_path + '/logo.jpg').convert_alpha()
    logo_img = pygame.transform.smoothscale(logo_img_org, (240, 105))
    instructions_img_org = pygame.image.load(
        asset_path + '/Instructions_for_playing_Caro_game.jpeg'
    ).convert()

    start_button = button.Button(970, 200, start_img, start_img, 0.8)
    pause_button = button.Button(970, 300, pause_img, pause_img, 0.8)
    replay_button = button.Button(970, 575, replay_img, replay_img, 0.8)
    exit_button = button.Button(970, 485, exit_img, exit_img, 0.8)
    undo_button = button.Button(970, 395, undo_img, undo_img, 0.8)
    ai_btn = button.Button(970, 305, ai_img, ai_img_gray, 0.8)
    person_btn = button.Button(1075, 305, person_img, person_img_gray, 0.8)
    h_btn = button.Button(1100, 235, h_img, h_img_gray, 0.8)
    m_btn = button.Button(1035, 235, m_img, m_img_gray, 0.8)
    e_btn = button.Button(970, 235, e_img, e_img_gray, 0.8)
    grand_master_btn = button.Button(1165, 235, gm_img, gm_img_gray, 0.8)
    ai_thinking_btn = button.Button(
        1020, 30, ai_thinking_img, ai_thinking_img_gray, 0.8)
    pvp_btn = button.Button(1075, 145, pvp_img, pvp_img_gray, 0.8)
    aivp_btn = button.Button(970, 145, aivp_img, aivp_img_gray, 0.8)
    logo_btn = button.Button(990, 660, logo_img, logo_img, 0.6)

    person_btn.disable_button()
    aivp_btn.disable_button()
    ai_thinking_btn.disable_button()
    if game_mode is not GameMode.NORMAL:
        aivp_btn.disable_button()
        pvp_btn.disable_button()
        ai_btn.disable_button()
        person_btn.disable_button()
        h_btn.disable_button()
        m_btn.disable_button()
        e_btn.disable_button()
        grand_master_btn.disable_button()
        ai_thinking_btn.disable_button()
    else:
        h_btn.enable_button()
        m_btn.enable_button()
        e_btn.enable_button()
        grand_master_btn.enable_button()
        if normal_mode_difficulty == 'grand_master':
            grand_master_btn.disable_button()
        elif normal_mode_difficulty == 'hard':
            h_btn.disable_button()
        elif normal_mode_difficulty == 'medium':
            m_btn.disable_button()
        else:
            e_btn.disable_button()

    pygame.display.set_caption('Caro game by MonHau VD')
    pygame.display.set_icon(icon_img)

    my_game = caro.Caro(ROWNUM, COLNUM, winning_condition, XO)
    my_game.use_ai(True)
    my_game.change_hard_ai('hard' if normal_mode_difficulty == 'grand_master' else normal_mode_difficulty)
    agent = build_player_vs_ai_agent()
    agent1 = Agent(
        max_depth=dev_mode_setup['ai_1_depth'],
        XO=dev_mode_setup['ai_1'],
        config=dev_mode_setup['ai_1_config'],
    )
    agent2 = Agent(
        max_depth=dev_mode_setup['ai_2_depth'],
        XO=dev_mode_setup['ai_2'],
        config=dev_mode_setup['ai_2_config'],
    )

    done = False
    status = my_game.get_winner()
    clock = pygame.time.Clock()
    turn_started_at = time.perf_counter()
    turn_elapsed_frozen = None
    turn_timer_paused = False
    turn_elapsed_paused = 0.0
    ai_is_thinking = False
    ai_future = None
    dev_future = None
    ai_executor = ProcessPoolExecutor(max_workers=1)
    bench_sess.benchmark_warm_executor(ai_executor, 1)
    benchmark_state = {
        'initialized': False,
        'running': False,
        'matchup_idx': 0,
        'game_idx': 0,
        'resume_matchup_idx': 0,
        'resume_game_idx': 0,
        'game_active': False,
        'game_ended_at': None,
        'current': None,
        'stats': {},
        'results': [],
        'parallel_workers': 1,
        'parallel_total': 0,
        'parallel_done': 0,
        'slots': [],
        'bench_slots_n': 0,
        'task_queue': deque(),
        'bench_session_started': False,
        'bench_paused': False,
        '_rownum': ROWNUM,
        '_colnum': COLNUM,
        '_winning_condition': winning_condition,
        '_xo': XO,
        '_summary_path': BENCHMARK_RESULT_SUMMARY_FILE,
        '_board_path': BENCHMARK_RESULT_BOARD_FILE,
        '_moves_path': BENCHMARK_RESULT_MOVES_FILE,
        '_fragments_dir': BENCHMARK_FRAGMENTS_DIR,
    }

    def _bench_get_executor():
        global ai_executor
        return ai_executor

    def _bench_set_executor(ex):
        global ai_executor
        ai_executor = ex

    def _bench_set_thinking(v: bool):
        global ai_is_thinking
        ai_is_thinking = v

    bench_rt = bench_sess.BenchRuntime(
        get_executor=_bench_get_executor,
        set_executor=_bench_set_executor,
        compute_ai_move_worker=compute_ai_move_worker,
        ai_thinking_btn=ai_thinking_btn,
        set_ai_is_thinking=_bench_set_thinking,
    )

    update_layout(Window_size[0], Window_size[1])


# ----------------------- Function ------------------------------------
def update_layout(new_width: int, new_height: int):
    global Window_size, WIDTH, HEIGHT, MARGIN
    global BOARD_OFFSET_X, BOARD_OFFSET_Y, PANEL_X, x_img, o_img

    if (
        game_mode is GameMode.BENCHMARK
        and benchmark_state.get('initialized')
        and benchmark_state.get('parallel_workers', 1) > 1
    ):
        bench_sess.ensure_benchmark_slots(
            benchmark_state,
            benchmark_state['parallel_workers'],
            ROWNUM,
            COLNUM,
            winning_condition,
            XO,
        )

    layout_globals: dict = {}
    normal_assets = {
        'x_img_org': x_img_org,
        'o_img_org': o_img_org,
        'start_button': start_button,
        'pause_button': pause_button,
        'replay_button': replay_button,
        'exit_button': exit_button,
        'undo_button': undo_button,
        'ai_btn': ai_btn,
        'person_btn': person_btn,
        'h_btn': h_btn,
        'm_btn': m_btn,
        'e_btn': e_btn,
        'grand_master_btn': grand_master_btn,
        'ai_thinking_btn': ai_thinking_btn,
        'pvp_btn': pvp_btn,
        'aivp_btn': aivp_btn,
        'logo_btn': logo_btn,
        'start_img_org': start_img_org,
        'pause_img_org': pause_img_org,
        'replay_img_org': replay_img_org,
        'exit_img_org': exit_img_org,
        'undo_img_org': undo_img_org,
        'ai_img_org': ai_img_org,
        'person_img_org': person_img_org,
        'ai_img_gray_org': ai_img_gray_org,
        'person_img_gray_org': person_img_gray_org,
        'h_img_org': h_img_org,
        'h_img_gray_org': h_img_gray_org,
        'm_img_org': m_img_org,
        'm_img_gray_org': m_img_gray_org,
        'e_img_org': e_img_org,
        'e_img_gray_org': e_img_gray_org,
        'gm_img_org': gm_img_org,
        'gm_img_gray_org': gm_img_gray_org,
        'pvp_img_org': pvp_img_org,
        'pvp_img_gray_org': pvp_img_gray_org,
        'aivp_img_org': aivp_img_org,
        'aivp_img_gray_org': aivp_img_gray_org,
        'ai_thinking_img_org': ai_thinking_img_org,
        'ai_thinking_img_gray_org': ai_thinking_img_gray_org,
        'logo_img_org': logo_img_org,
    }
    benchmark_bar_assets = {
        'start_button': start_button,
        'pause_button': pause_button,
        'replay_button': replay_button,
        'exit_button': exit_button,
        'start_img': start_img,
        'pause_img': pause_img,
        'replay_img': replay_img,
        'start_img_org': start_img_org,
        'pause_img_org': pause_img_org,
        'replay_img_org': replay_img_org,
        'x_img_org': x_img_org,
        'o_img_org': o_img_org,
    }
    ui_layout.update_window_layout(
        new_width,
        new_height,
        game_mode=game_mode,
        benchmark_state=benchmark_state,
        colnum=COLNUM,
        rownum=ROWNUM,
        window_size_mut=Window_size,
        layout_globals=layout_globals,
        normal_assets=normal_assets,
        benchmark_bar_assets=benchmark_bar_assets,
    )
    if not (
        game_mode is GameMode.BENCHMARK
        and benchmark_state.get('initialized')
        and benchmark_state.get('parallel_workers', 1) > 1
    ):
        MARGIN = layout_globals['MARGIN']
        WIDTH = layout_globals['WIDTH']
        HEIGHT = layout_globals['HEIGHT']
        BOARD_OFFSET_X = layout_globals['BOARD_OFFSET_X']
        BOARD_OFFSET_Y = layout_globals['BOARD_OFFSET_Y']
        PANEL_X = layout_globals['PANEL_X']
        x_img = layout_globals['x_img']
        o_img = layout_globals['o_img']


def logo():
    font = pygame.font.Font('freesansbold.ttf', 36)
    small_font = pygame.font.Font('freesansbold.ttf', 24)
    text = font.render('By MonHau VD', True, WHITE, BLACK)
    textRect = text.get_rect()
    textRect.center = (PANEL_X + 150, Window_size[1] - 20)
    Screen.blit(text, textRect)
    # logo_btn.draw(Screen)
    if game_mode is GameMode.DEVELOPER:
        font = pygame.font.Font('freesansbold.ttf', 36)
        text = font.render('Developer_Mode', True, WHITE, BLACK)
        textRect = text.get_rect()
        textRect.center = (PANEL_X + 140, 160)
        Screen.blit(text, textRect)
    elif game_mode is GameMode.BENCHMARK:
        font = pygame.font.Font('freesansbold.ttf', 36)
        text = font.render('Benchmark_Mode', True, WHITE, BLACK)
        textRect = text.get_rect()
        textRect.center = (PANEL_X + 140, 160)
        Screen.blit(text, textRect)
    if status == -1:
        if turn_timer_paused:
            elapsed = turn_elapsed_paused
        else:
            elapsed = time.perf_counter() - turn_started_at
    else:
        elapsed = turn_elapsed_frozen if turn_elapsed_frozen is not None else 0.0
    turn_x = PANEL_X + 170
    turn_y = 68
    # Xóa vùng đồng hồ trước khi vẽ frame mới để tránh lưu vết ký tự cũ.
    pygame.draw.rect(Screen, BLACK, (turn_x, turn_y, 220, 30))
    turn_text = small_font.render(f"Turn {my_game.XO}: {elapsed:.1f}s", True, WHITE, BLACK)
    Screen.blit(turn_text, (turn_x, turn_y))


def apply_move_with_timer(this_game: caro.Caro, row: int, col: int, actor: str = "unknown"):
    global turn_started_at
    before_len = len(this_game.last_move)
    moved_piece = this_game.XO
    elapsed = time.perf_counter() - turn_started_at
    this_game.make_move(row, col)
    if len(this_game.last_move) > before_len:
        now = time.perf_counter()
        turn_started_at = now
        set_turn_timer_pause(False)
        print(f"[MOVE] actor={actor}; piece={moved_piece}; elapsed={elapsed:.3f}s; coord=({row},{col})")
        return elapsed
    return None


def update_game_status(new_status: int):
    global status, turn_started_at, turn_elapsed_frozen
    if new_status != -1 and status == -1:
        turn_elapsed_frozen = time.perf_counter() - turn_started_at
    elif new_status == -1 and status != -1:
        turn_started_at = time.perf_counter()
        turn_elapsed_frozen = None
    status = new_status


def set_turn_timer_pause(is_paused: bool):
    global turn_timer_paused, turn_elapsed_paused, turn_started_at
    if is_paused and not turn_timer_paused:
        turn_elapsed_paused = time.perf_counter() - turn_started_at
        turn_timer_paused = True
    elif (not is_paused) and turn_timer_paused:
        turn_started_at = time.perf_counter() - turn_elapsed_paused
        turn_timer_paused = False


def benchmark_setup_game():
    global agent1, agent2, turn_started_at, turn_elapsed_frozen, dev_future, ai_is_thinking
    matchup = benchmark_setup['matchups'][benchmark_state['matchup_idx']]
    game_idx = benchmark_state['game_idx']
    match_id = f"{matchup['name']}__game_{game_idx + 1}"

    agent1, agent2, cur = bench_sess.make_matchup_setup(
        benchmark_setup, benchmark_state['matchup_idx'], game_idx, my_game
    )
    benchmark_state['current'] = cur
    gpm = max(1, int(benchmark_setup.get('games_per_matchup', 1)))
    game_seq = benchmark_state['matchup_idx'] * gpm + benchmark_state['game_idx'] + 1
    bench_sess.benchmark_on_new_game_begin(benchmark_state, cur, game_seq)
    update_game_status(my_game.get_winner())
    turn_started_at = time.perf_counter()
    turn_elapsed_frozen = None
    set_turn_timer_pause(False)

    benchmark_state['game_active'] = True
    benchmark_state['game_ended_at'] = None
    if dev_future is not None:
        dev_future.cancel()
        dev_future = None
    ai_is_thinking = False
    total_pairs = len(benchmark_setup['matchups'])
    total_games_per_pair = max(1, int(benchmark_setup.get('games_per_matchup', 1)))
    pair_no = benchmark_state['matchup_idx'] + 1
    game_no = game_idx + 1
    print(
        f"[BENCH] starting game: match_id={match_id} "
        f"(pair={pair_no}/{total_pairs}, game={game_no}/{total_games_per_pair})"
    )


def benchmark_finalize_game():
    bench_sess.benchmark_finalize_from_game(
        benchmark_setup,
        benchmark_state,
        BENCHMARK_RESULT_SUMMARY_FILE,
        BENCHMARK_RESULT_BOARD_FILE,
        my_game,
        benchmark_state['current'],
        bump_parallel_done=False,
    )


def draw(this_game: caro.Caro, this_screen):
    logo()
    for row in range(ROWNUM):
        for column in range(COLNUM):
            color = WHITE
            if len(this_game.last_move) > 0:
                last_move_row, last_move_col = this_game.last_move[-1][0], this_game.last_move[-1][1]
                if row == last_move_row and column == last_move_col:
                    color = GREEN
            pygame.draw.rect(this_screen,
                             color,
                             [BOARD_OFFSET_X + (MARGIN + WIDTH) * column + MARGIN,
                              BOARD_OFFSET_Y + (MARGIN + HEIGHT) * row + MARGIN,
                              WIDTH,
                              HEIGHT])
            if this_game.grid[row][column] == 'X':
                this_screen.blit(
                    x_img, (BOARD_OFFSET_X + (WIDTH + MARGIN) * column + MARGIN,
                            BOARD_OFFSET_Y + (HEIGHT + MARGIN) * row + MARGIN))
            if this_game.grid[row][column] == 'O':
                this_screen.blit(
                    o_img, (BOARD_OFFSET_X + (WIDTH + MARGIN) * column + MARGIN,
                            BOARD_OFFSET_Y + (HEIGHT + MARGIN) * row + MARGIN))


def re_draw():
    logo()
    Screen.fill(BLACK)
    for row in range(ROWNUM):
        for column in range(COLNUM):
            color = WHITE
            pygame.draw.rect(Screen,
                             color,
                             [BOARD_OFFSET_X + (MARGIN + WIDTH) * column + MARGIN,
                              BOARD_OFFSET_Y + (MARGIN + HEIGHT) * row + MARGIN,
                              WIDTH,
                              HEIGHT])


def Undo(self: caro.Caro):
    re_draw()
    if self.is_use_ai:
        if len(self.last_move) > 2:
            last_move = self.last_move[-1]
            last_move_2 = self.last_move[-2]
            self.last_move.pop()
            self.last_move.pop()
            # print(self.last_move)
            # print(last_move, type(last_move), type(last_move[0]))
            row = int(last_move[0])
            col = int(last_move[1])
            row2 = int(last_move_2[0])
            col2 = int(last_move_2[1])
            self.grid[row][col] = '.'
            self.grid[row2][col2] = '.'
            draw(my_game, Screen)
    else:
        if len(self.last_move) > 0:
            last_move = self.last_move[-1]
            self.last_move.pop()
            # print(self.last_move)
            # print(last_move, type(last_move), type(last_move[0]))
            row = int(last_move[0])
            col = int(last_move[1])
            self.grid[row][col] = '.'
            if self.XO == 'X':
                self.XO = 'O'
            else:
                self.XO = 'X'
            if self.turn == 1:
                self.turn = 2
            else:
                self.turn = 1
            draw(my_game, Screen)
    pass


def checking_winning(status):
    if status == 2:
        font = pygame.font.Font('freesansbold.ttf', 100)
        text = font.render('Draw', True, GREEN, BLUE)
        textRect = text.get_rect()
        textRect.center = (int(Window_size[0]/2), int(Window_size[1]/2))
        Screen.blit(text, textRect)
        # done = True
    if status == 0:
        font = pygame.font.Font('freesansbold.ttf', 100)
        text = font.render('X win', True, RED, GREEN)
        textRect = text.get_rect()
        textRect.center = (int(Window_size[0]/2), int(Window_size[1]/2))
        Screen.blit(text, textRect)
        # done = True
    if status == 1:
        font = pygame.font.Font('freesansbold.ttf', 100)
        text = font.render('O win', True, BLUE, GREEN)
        textRect = text.get_rect()
        textRect.center = (int(Window_size[0]/2), int(Window_size[1]/2))
        Screen.blit(text, textRect)
        # done = True


# --------- Main Program Loop -------------------------------------------
def main(argv: list[str] | None = None):
    global done, ai_is_thinking, ai_future, dev_future, ai_executor
    global normal_mode_difficulty, agent, turn_elapsed_paused, turn_started_at, turn_elapsed_frozen
    global game_mode, dev_mode_setup, agent1, agent2

    args = parse_args(argv)
    if args.bench_export_merge:
        run_benchmark_export_merge_cli(args)
        return

    if args.dev:
        game_mode = GameMode.DEVELOPER
    elif args.benchmark:
        game_mode = GameMode.BENCHMARK
    else:
        game_mode = GameMode.NORMAL

    if args.dev:
        dev_path = args.dev_config if args.dev_config is not None else DEV_MODE_CONFIG_FILE
        load_dev_mode_config(dev_path, explicit_file=args.dev_config is not None)
    else:
        dev_mode_setup = copy.deepcopy(_DEFAULT_DEV_MODE_SETUP)

    bench_path = args.benchmark_config if args.benchmark_config is not None else BENCHMARK_CONFIG_FILE
    bench_sess.load_benchmark_config(
        benchmark_setup,
        bench_path,
        default_config_file=BENCHMARK_CONFIG_FILE,
        must_exist=(game_mode is GameMode.BENCHMARK),
    )

    init_application()
    if game_mode is GameMode.BENCHMARK:

        def _benchmark_sigint_handler(_sig, _frame):
            try:
                bench_sess.export_benchmark_fragments_if_any(
                    BENCHMARK_RESULT_SUMMARY_FILE,
                    BENCHMARK_RESULT_BOARD_FILE,
                    BENCHMARK_RESULT_MOVES_FILE,
                    BENCHMARK_FRAGMENTS_DIR,
                )
                print("[BENCH] đã gộp fragments → master (Ctrl+C)", file=sys.stderr)
            except Exception as ex:
                print(f"[BENCH] gộp khi Ctrl+C thất bại: {ex}", file=sys.stderr)
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, _benchmark_sigint_handler)

    benchmark_cfg_default_file = os.path.join(CONFIG_DIR, "benchmark_config_default.json")
    dropdown_open = False
    active_modal: str | None = None
    active_text_field: str | None = None
    benchmark_path_input = os.path.join(menu_overlay.default_desktop_dir(), "benchmark_config.json")
    benchmark_workers_input = str(max(1, min(int(args.benchmark_workers), 32)))
    modal_message = ""
    modal_message_is_error = False
    show_benchmark_guide = False
    error_modal_message = ""
    error_modal_return_to = "benchmark"
    cursor_pos_by_field: dict[str, int] = {}
    bool_flash_until_ms: dict[str, int] = {}

    try:
        with open(benchmark_cfg_default_file, "r", encoding="utf-8") as f:
            benchmark_default_cfg = json.load(f)
    except Exception:
        benchmark_default_cfg = {}
    custom_agents = benchmark_default_cfg.get("custom_agents", {}) if isinstance(benchmark_default_cfg, dict) else {}
    preset_names = sorted(custom_agents.keys()) if isinstance(custom_agents, dict) else []
    if not preset_names:
        preset_names = ["depth_7", "depth_8_beam_b_180s_timer"]
    dev_left_preset_idx = 0
    dev_right_preset_idx = 1 if len(preset_names) > 1 else 0
    dev_left_depth = "7"
    dev_right_depth = "8"
    dev_left_cfg_fields: dict[str, str] = {
        "use_cython_search": "false",
        "use_tss": "false",
        "use_lazy_smp": "false",
        "beam_width_root": "0",
        "beam_width_inner": "0",
        "move_time_budget_sec": "20",
    }
    dev_right_cfg_fields: dict[str, str] = copy.deepcopy(dev_left_cfg_fields)
    dev_left_dropdown_open = False
    dev_right_dropdown_open = False
    dev_left_dropdown_scroll = 0
    dev_right_dropdown_scroll = 0
    dev_dropdown_visible_rows = 8
    custom_preset_idx = 0
    custom_dropdown_open = False
    custom_dropdown_scroll = 0
    custom_depth = "8"
    custom_cfg_fields: dict[str, str] = {
        "use_cython_search": "false",
        "use_tss": "false",
        "use_lazy_smp": "false",
        "beam_width_root": "0",
        "beam_width_inner": "0",
        "move_time_budget_sec": "20",
    }
    custom_ai_setup = {
        "preset_name": "custom",
        "depth": 8,
        "config": {
            "use_cython_search": False,
            "use_tss": False,
            "use_lazy_smp": False,
            "beam_width_root": 0,
            "beam_width_inner": 0,
            "move_time_budget_sec": 20,
        },
    }

    def _apply_preset_to_dev(side: str):
        nonlocal dev_left_depth, dev_right_depth, dev_left_cfg_fields, dev_right_cfg_fields, dev_left_preset_idx, dev_right_preset_idx
        idx = dev_left_preset_idx if side == "left" else dev_right_preset_idx
        if not preset_names:
            return
        name = preset_names[idx]
        preset = custom_agents.get(name, {})
        depth = preset.get("depth", 7)
        cfg = preset.get("config", {})
        if side == "left":
            dev_left_depth = str(depth)
            dev_left_cfg_fields = custom_ai_ui.cfg_to_fields(cfg if isinstance(cfg, dict) else {})
        else:
            dev_right_depth = str(depth)
            dev_right_cfg_fields = custom_ai_ui.cfg_to_fields(cfg if isinstance(cfg, dict) else {})

    def _apply_preset_to_custom():
        nonlocal custom_preset_idx, custom_depth, custom_cfg_fields
        if not preset_names:
            return
        name = preset_names[custom_preset_idx]
        preset = custom_agents.get(name, {})
        custom_depth = str(preset.get("depth", 8))
        custom_cfg_fields = custom_ai_ui.cfg_to_fields(preset.get("config", {}))

    _apply_preset_to_dev("left")
    _apply_preset_to_dev("right")
    _apply_preset_to_custom()

    def _set_mode_ui():
        if game_mode is GameMode.NORMAL:
            aivp_btn.disable_button() if my_game.is_use_ai else pvp_btn.disable_button()
            if my_game.is_use_ai:
                pvp_btn.enable_button()
            else:
                aivp_btn.enable_button()
            ai_btn.enable_button()
            person_btn.enable_button()
            h_btn.enable_button()
            m_btn.enable_button()
            e_btn.enable_button()
            grand_master_btn.enable_button()
            if normal_mode_difficulty == "easy":
                e_btn.disable_button()
            elif normal_mode_difficulty == "medium":
                m_btn.disable_button()
            elif normal_mode_difficulty == "hard":
                h_btn.disable_button()
            else:
                grand_master_btn.disable_button()
        elif game_mode is GameMode.CUSTOM_AI:
            my_game.use_ai(True)
            aivp_btn.disable_button()
            pvp_btn.disable_button()
            ai_btn.enable_button()
            person_btn.enable_button()
            h_btn.disable_button()
            m_btn.disable_button()
            e_btn.disable_button()
            grand_master_btn.disable_button()
        else:
            aivp_btn.disable_button()
            pvp_btn.disable_button()
            ai_btn.disable_button()
            person_btn.disable_button()
            h_btn.disable_button()
            m_btn.disable_button()
            e_btn.disable_button()
            grand_master_btn.disable_button()

    def _refresh_full_screen_after_mode_switch():
        # Force full repaint once to avoid stale modal/menu artifacts.
        Screen.fill(BLACK)
        re_draw()
        draw(my_game, Screen)
        checking_winning(status)
        pygame.display.update()

    def _close_modal_and_refresh():
        nonlocal active_modal, active_text_field
        active_modal = None
        active_text_field = None
        _refresh_full_screen_after_mode_switch()

    def _show_error_modal(message: str, *, return_to: str = "benchmark"):
        nonlocal active_modal, error_modal_message, error_modal_return_to
        error_modal_message = message
        error_modal_return_to = return_to
        active_modal = "error"

    def _get_field_value(field_name: str) -> str:
        if field_name == "dev_left_depth":
            return dev_left_depth
        if field_name == "dev_right_depth":
            return dev_right_depth
        if field_name == "custom_depth":
            return custom_depth
        if field_name == "benchmark_path":
            return benchmark_path_input
        if field_name == "benchmark_workers":
            return benchmark_workers_input
        if field_name.startswith("dev_left_"):
            key = field_name.replace("dev_left_", "", 1)
            return dev_left_cfg_fields.get(key, "")
        if field_name.startswith("dev_right_"):
            key = field_name.replace("dev_right_", "", 1)
            return dev_right_cfg_fields.get(key, "")
        if field_name.startswith("custom_"):
            key = field_name.replace("custom_", "", 1)
            return custom_cfg_fields.get(key, "")
        return ""

    def _set_field_value(field_name: str, value: str) -> None:
        nonlocal dev_left_depth, dev_right_depth, custom_depth, benchmark_path_input, benchmark_workers_input
        if field_name == "dev_left_depth":
            dev_left_depth = value
            return
        if field_name == "dev_right_depth":
            dev_right_depth = value
            return
        if field_name == "custom_depth":
            custom_depth = value
            return
        if field_name == "benchmark_path":
            benchmark_path_input = value
            return
        if field_name == "benchmark_workers":
            benchmark_workers_input = value
            return
        if field_name.startswith("dev_left_"):
            key = field_name.replace("dev_left_", "", 1)
            dev_left_cfg_fields[key] = value
            return
        if field_name.startswith("dev_right_"):
            key = field_name.replace("dev_right_", "", 1)
            dev_right_cfg_fields[key] = value
            return
        if field_name.startswith("custom_"):
            key = field_name.replace("custom_", "", 1)
            custom_cfg_fields[key] = value

    def _focus_field(field_name: str) -> None:
        nonlocal active_text_field
        active_text_field = field_name
        cursor_pos_by_field[field_name] = len(_get_field_value(field_name))

    def _resolve_benchmark_cfg_path(path_input: str) -> str:
        p = (path_input or "").strip()
        if not p:
            return os.path.join(menu_overlay.default_desktop_dir(), "benchmark_config.json")
        if p.endswith(".json"):
            return p
        return os.path.join(p, "benchmark_config.json")

    def _switch_to_normal_mode():
        nonlocal active_modal
        global game_mode
        if ai_future is not None:
            ai_future.cancel()
        if dev_future is not None:
            dev_future.cancel()
        my_game.reset()
        update_game_status(my_game.get_winner())
        game_mode = GameMode.NORMAL
        active_modal = None
        _set_mode_ui()
        update_layout(Window_size[0], Window_size[1])
        _refresh_full_screen_after_mode_switch()

    def _start_dev_mode_from_modal():
        nonlocal active_modal, modal_message
        global game_mode, agent1, agent2
        try:
            left_depth = max(1, int(dev_left_depth.strip()))
            right_depth = max(1, int(dev_right_depth.strip()))
            left_cfg = custom_ai_ui.fields_to_cfg(dev_left_cfg_fields)
            right_cfg = custom_ai_ui.fields_to_cfg(dev_right_cfg_fields)
        except Exception as ex:
            modal_message = f"Invalid dev settings: {ex}"
            return
        dev_mode_setup["ai_1"] = "X"
        dev_mode_setup["ai_2"] = "O"
        dev_mode_setup["ai_1_depth"] = left_depth
        dev_mode_setup["ai_2_depth"] = right_depth
        dev_mode_setup["ai_1_config"] = left_cfg
        dev_mode_setup["ai_2_config"] = right_cfg
        dev_mode_setup["start"] = True
        dev_mode_setup["pause"] = False
        agent1 = Agent(max_depth=left_depth, XO="X", config=left_cfg)
        agent2 = Agent(max_depth=right_depth, XO="O", config=right_cfg)
        my_game.reset()
        update_game_status(my_game.get_winner())
        game_mode = GameMode.DEVELOPER
        active_modal = None
        _set_mode_ui()
        update_layout(Window_size[0], Window_size[1])
        _refresh_full_screen_after_mode_switch()

    def _start_custom_mode_from_modal():
        nonlocal active_modal, modal_message, custom_ai_setup
        global game_mode, agent
        try:
            depth = max(1, int(custom_depth.strip()))
            cfg = custom_ai_ui.fields_to_cfg(custom_cfg_fields)
        except Exception as ex:
            modal_message = f"Invalid custom AI settings: {ex}"
            return
        preset_name = preset_names[custom_preset_idx] if preset_names else "custom"
        custom_ai_setup = {
            "preset_name": preset_name,
            "depth": depth,
            "config": cfg,
        }
        my_game.reset()
        my_game.use_ai(True)
        my_game.set_ai_turn(2)
        person_btn.disable_button()
        ai_btn.enable_button()
        agent = build_custom_ai_agent(custom_ai_setup)
        update_game_status(my_game.get_winner())
        game_mode = GameMode.CUSTOM_AI
        active_modal = None
        _set_mode_ui()
        update_layout(Window_size[0], Window_size[1])
        _refresh_full_screen_after_mode_switch()

    def _start_benchmark_mode():
        nonlocal active_modal, modal_message, modal_message_is_error, benchmark_path_input, benchmark_workers_input
        global game_mode
        global BENCHMARK_RESULT_SUMMARY_FILE, BENCHMARK_RESULT_BOARD_FILE, BENCHMARK_RESULT_MOVES_FILE, BENCHMARK_FRAGMENTS_DIR
        modal_message = ""
        modal_message_is_error = False
        cfg_path = _resolve_benchmark_cfg_path(benchmark_path_input)
        benchmark_path_input = cfg_path
        try:
            bw = max(1, min(int((benchmark_workers_input or "1").strip()), 32))
        except Exception:
            modal_message = "Invalid workers value (must be integer 1..32)."
            modal_message_is_error = True
            active_modal = "benchmark"
            return
        args.benchmark_workers = bw
        cfg_dir = os.path.dirname(cfg_path)
        try:
            if cfg_dir:
                os.makedirs(cfg_dir, exist_ok=True)
        except Exception as ex:
            modal_message = f"Invalid config path: cannot create directory. {ex}"
            modal_message_is_error = True
            active_modal = "benchmark"
            return
        if not os.path.isfile(cfg_path):
            modal_message = f"Config file not found: {cfg_path}"
            modal_message_is_error = True
            active_modal = "benchmark"
            return
        try:
            bench_sess.load_benchmark_config(
                benchmark_setup,
                cfg_path,
                default_config_file=BENCHMARK_CONFIG_FILE,
                must_exist=True,
            )
        except Exception as ex:
            modal_message = f"Failed loading benchmark config: {ex}"
            modal_message_is_error = True
            active_modal = "benchmark"
            return

        # Menu BenchmarkMode: always export to sibling "result" folder beside chosen config file.
        cfg_parent_dir = os.path.dirname(cfg_path) or menu_overlay.default_desktop_dir()
        results_dir = os.path.join(cfg_parent_dir, "result")
        os.makedirs(results_dir, exist_ok=True)
        benchmark_setup["output_dir"] = results_dir
        BENCHMARK_RESULT_SUMMARY_FILE = os.path.join(results_dir, "benchmark_results_summary.txt")
        BENCHMARK_RESULT_BOARD_FILE = os.path.join(results_dir, "benchmark_results_boards.txt")
        BENCHMARK_RESULT_MOVES_FILE = os.path.join(results_dir, "benchmark_results_moves.txt")
        BENCHMARK_FRAGMENTS_DIR = os.path.join(results_dir, "fragments")
        os.makedirs(BENCHMARK_FRAGMENTS_DIR, exist_ok=True)
        benchmark_state["_summary_path"] = BENCHMARK_RESULT_SUMMARY_FILE
        benchmark_state["_board_path"] = BENCHMARK_RESULT_BOARD_FILE
        benchmark_state["_moves_path"] = BENCHMARK_RESULT_MOVES_FILE
        benchmark_state["_fragments_dir"] = BENCHMARK_FRAGMENTS_DIR
        my_game.reset()
        update_game_status(my_game.get_winner())
        benchmark_state["initialized"] = False
        benchmark_state["running"] = False
        benchmark_state["matchup_idx"] = 0
        benchmark_state["game_idx"] = 0
        benchmark_state["resume_matchup_idx"] = 0
        benchmark_state["resume_game_idx"] = 0
        benchmark_state["stats"] = {}
        benchmark_state["results"] = []
        game_mode = GameMode.BENCHMARK
        active_modal = None
        _set_mode_ui()
        update_layout(Window_size[0], Window_size[1])
        _refresh_full_screen_after_mode_switch()

    while not done:
        if game_mode is GameMode.BENCHMARK and not benchmark_state['initialized']:
            benchmark_state['initialized'] = True
            benchmark_state['running'] = False
            resume_matchup_idx, resume_game_idx = bench_sess.detect_benchmark_resume_position(
                benchmark_setup,
                BENCHMARK_RESULT_SUMMARY_FILE,
                BENCHMARK_FRAGMENTS_DIR,
            )
            benchmark_state['resume_matchup_idx'] = resume_matchup_idx
            benchmark_state['resume_game_idx'] = resume_game_idx
            benchmark_state['matchup_idx'] = resume_matchup_idx
            benchmark_state['game_idx'] = resume_game_idx
            benchmark_state['stats'] = {}
            benchmark_state['results'] = []
            my_game.reset()
            update_game_status(my_game.get_winner())
            set_turn_timer_pause(True)
            pw = max(1, min(int(args.benchmark_workers), 32))
            benchmark_state['parallel_workers'] = pw
            if pw > 1:
                bench_sess.ensure_benchmark_slots(
                    benchmark_state, pw, ROWNUM, COLNUM, winning_condition, XO
                )
                update_layout(Window_size[0], Window_size[1])
                print(
                    f"[BENCH] {pw} bàn cờ trong một cửa sổ; mỗi bàn có Start/Pause/Replay riêng. "
                    "Dùng --benchmark-workers 1 để một bàn như trước."
                )
            print("[BENCH] waiting for Start button")

        if game_mode is GameMode.BENCHMARK:
            if benchmark_state['running'] and benchmark_state['parallel_workers'] > 1:
                bench_sess.benchmark_multi_tick_slots(benchmark_setup, benchmark_state, bench_rt)
            elif (
                benchmark_state['running']
                and benchmark_state['parallel_workers'] <= 1
                and benchmark_state['matchup_idx'] < len(benchmark_setup['matchups'])
            ):
                if status == -1:
                    if dev_future is None:
                        ai_is_thinking = True
                        ai_thinking_btn.enable_button()
                        snapshot = copy.deepcopy(my_game)
                        current_agent = agent1 if my_game.turn == 1 else agent2
                        dev_future = ai_executor.submit(
                            compute_ai_move_worker,
                            snapshot,
                            current_agent.max_depth,
                            current_agent.XO,
                            current_agent.get_runtime_config(),
                        )
                    elif dev_future.done():
                        ai_is_thinking = False
                        ai_thinking_btn.disable_button()
                        try:
                            best_move = dev_future.result()
                            if best_move is not None:
                                current_actor = benchmark_state['current']['x_label'] if my_game.turn == 1 else benchmark_state['current']['o_label']
                                br, bc = best_move[0], best_move[1]
                                piece = my_game.XO
                                elapsed = apply_move_with_timer(my_game, br, bc, actor=current_actor)
                                bench_sess.benchmark_record_move(
                                    benchmark_state,
                                    current_actor,
                                    elapsed,
                                    row=br,
                                    col=bc,
                                    piece=piece,
                                )
                                update_game_status(my_game.get_winner())
                        finally:
                            dev_future = None
                else:
                    if benchmark_state['game_ended_at'] is None:
                        benchmark_finalize_game()
                        benchmark_state['game_ended_at'] = time.perf_counter()
                    elif time.perf_counter() - benchmark_state['game_ended_at'] > 0.8:
                        benchmark_state['game_idx'] += 1
                        if benchmark_state['game_idx'] >= benchmark_setup['games_per_matchup']:
                            benchmark_state['matchup_idx'] += 1
                            benchmark_state['game_idx'] = 0
                        if benchmark_state['matchup_idx'] < len(benchmark_setup['matchups']):
                            benchmark_setup_game()
                        else:
                            ai_is_thinking = False
                            ai_thinking_btn.disable_button()
                            benchmark_state['running'] = False
                            print("[BENCH] completed all matchups")
                            bench_sess.export_benchmark_merged_reports(
                                BENCHMARK_RESULT_SUMMARY_FILE,
                                BENCHMARK_RESULT_BOARD_FILE,
                                BENCHMARK_RESULT_MOVES_FILE,
                                BENCHMARK_FRAGMENTS_DIR,
                            )
                            for matchup_name, matchup_stats in benchmark_state['stats'].items():
                                print(f"[BENCH][{matchup_name}]")
                                for label, s in matchup_stats.items():
                                    avg = (s['move_time_total'] / s['move_count']) if s['move_count'] else 0.0
                                    print(f"  {label}: W={s['wins']} L={s['losses']} D={s['draws']} avg_move={avg:.3f}s")

        if (game_mode in (GameMode.NORMAL, GameMode.CUSTOM_AI) and my_game.is_use_ai and my_game.turn == my_game.ai_turn
                and status == -1):
            if ai_future is None:
                ai_is_thinking = True
                ai_thinking_btn.enable_button()
                snapshot = copy.deepcopy(my_game)
                ai_future = ai_executor.submit(
                    compute_ai_move_worker,
                    snapshot,
                    agent.max_depth,
                    agent.XO,
                    agent.get_runtime_config(),
                )
            elif ai_future.done():
                ai_is_thinking = False
                ai_thinking_btn.disable_button()
                try:
                    best_move = ai_future.result()
                    if best_move is not None:
                        apply_move_with_timer(my_game, best_move[0], best_move[1], actor="agent_AI")
                finally:
                    ai_future = None
                pygame.event.clear(pygame.MOUSEBUTTONDOWN)
                update_game_status(my_game.get_winner())
        else:
            if ai_future is not None and ai_future.done():
                ai_future = None
            if game_mode in (GameMode.NORMAL, GameMode.CUSTOM_AI):
                ai_is_thinking = False
                ai_thinking_btn.disable_button()

        if game_mode is GameMode.DEVELOPER and status == -1 and dev_mode_setup['start'] and not dev_mode_setup['pause']:
            if dev_future is None:
                ai_is_thinking = True
                ai_thinking_btn.enable_button()
                snapshot = copy.deepcopy(my_game)
                current_agent = agent1 if my_game.turn == 1 else agent2
                dev_future = ai_executor.submit(
                    compute_ai_move_worker,
                    snapshot,
                    current_agent.max_depth,
                    current_agent.XO,
                    current_agent.get_runtime_config(),
                )
            elif dev_future.done():
                ai_is_thinking = False
                ai_thinking_btn.disable_button()
                try:
                    best_move = dev_future.result()
                    if best_move is not None:
                        current_actor = "agent_1" if my_game.turn == 1 else "agent_2"
                        apply_move_with_timer(my_game, best_move[0], best_move[1], actor=current_actor)
                        update_game_status(my_game.get_winner())
                finally:
                    dev_future = None
        elif game_mode is GameMode.DEVELOPER:
            if dev_future is not None and dev_future.done():
                dev_future = None
            if not dev_mode_setup['start']:
                ai_is_thinking = False
                ai_thinking_btn.disable_button()

        menu_button_rect, menu_items, menu_item_rects = menu_overlay.top_menu_rects()

        for event in pygame.event.get():  # User did something
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if menu_button_rect.collidepoint(mx, my):
                    dropdown_open = not dropdown_open
                    continue
                if dropdown_open:
                    clicked_menu = False
                    for item_rect, item in zip(menu_item_rects, menu_items):
                        if item_rect.collidepoint(mx, my):
                            clicked_menu = True
                            dropdown_open = False
                            if item == "Help":
                                active_modal = "help"
                            elif item == "About":
                                active_modal = "about"
                            elif item == "NormalMode":
                                if game_mode is not GameMode.NORMAL:
                                    _switch_to_normal_mode()
                            elif item == "DevMode":
                                active_modal = "dev"
                            elif item == "CustomAI":
                                active_modal = "custom_ai"
                            elif item == "BenchMarkMode":
                                active_modal = "benchmark"
                            break
                    if clicked_menu:
                        continue
                    dropdown_open = False

                # Modal interactions (click outside to close for help/about/guide)
                if active_modal in ("help", "about", "benchmark_guide"):
                    panel_rect = pygame.Rect(80, 70, Window_size[0] - 160, Window_size[1] - 140)
                    if modal_close_button_rect(panel_rect).collidepoint(mx, my):
                        show_benchmark_guide = False
                        _close_modal_and_refresh()
                        continue
                    if not panel_rect.collidepoint(mx, my):
                        show_benchmark_guide = False
                        _close_modal_and_refresh()
                        continue

                if active_modal == "dev":
                    panel_rect = pygame.Rect(80, 70, Window_size[0] - 160, Window_size[1] - 140)
                    if modal_close_button_rect(panel_rect).collidepoint(mx, my):
                        _close_modal_and_refresh()
                        dev_left_dropdown_open = False
                        dev_right_dropdown_open = False
                        continue
                    if not panel_rect.collidepoint(mx, my):
                        _close_modal_and_refresh()
                        dev_left_dropdown_open = False
                        dev_right_dropdown_open = False
                        continue
                    left_preset_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 70, 300, 30)
                    right_preset_rect = pygame.Rect(panel_rect.centerx + 20, panel_rect.y + 70, 300, 30)
                    left_depth_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 120, 130, 30)
                    right_depth_rect = pygame.Rect(panel_rect.centerx + 20, panel_rect.y + 120, 130, 30)
                    start_rect = pygame.Rect(panel_rect.centerx - 70, panel_rect.bottom - 60, 140, 36)
                    cfg_keys = [
                        "use_cython_search",
                        "use_tss",
                        "use_lazy_smp",
                        "beam_width_root",
                        "beam_width_inner",
                        "move_time_budget_sec",
                    ]
                    bool_cfg_keys = {"use_cython_search", "use_tss", "use_lazy_smp"}
                    left_field_rects = {
                        key: pygame.Rect(panel_rect.x + 30, panel_rect.y + 170 + i * 42, panel_rect.width // 2 - 70, 30)
                        for i, key in enumerate(cfg_keys)
                    }
                    right_field_rects = {
                        key: pygame.Rect(panel_rect.centerx + 20, panel_rect.y + 170 + i * 42, panel_rect.width // 2 - 70, 30)
                        for i, key in enumerate(cfg_keys)
                    }
                    left_dropdown_rects = [
                        pygame.Rect(left_preset_rect.x, left_preset_rect.bottom + i * 28, left_preset_rect.width, 28)
                        for i in range(min(len(preset_names), dev_dropdown_visible_rows))
                    ]
                    right_dropdown_rects = [
                        pygame.Rect(right_preset_rect.x, right_preset_rect.bottom + i * 28, right_preset_rect.width, 28)
                        for i in range(min(len(preset_names), dev_dropdown_visible_rows))
                    ]

                    if left_preset_rect.collidepoint(mx, my):
                        dev_left_dropdown_open = not dev_left_dropdown_open
                        dev_right_dropdown_open = False
                    elif right_preset_rect.collidepoint(mx, my):
                        dev_right_dropdown_open = not dev_right_dropdown_open
                        dev_left_dropdown_open = False
                    elif dev_left_dropdown_open and any(r.collidepoint(mx, my) for r in left_dropdown_rects):
                        for i, r in enumerate(left_dropdown_rects):
                            if r.collidepoint(mx, my):
                                dev_left_preset_idx = min(
                                    dev_left_dropdown_scroll + i,
                                    max(0, len(preset_names) - 1),
                                )
                                _apply_preset_to_dev("left")
                                break
                        dev_left_dropdown_open = False
                    elif dev_right_dropdown_open and any(r.collidepoint(mx, my) for r in right_dropdown_rects):
                        for i, r in enumerate(right_dropdown_rects):
                            if r.collidepoint(mx, my):
                                dev_right_preset_idx = min(
                                    dev_right_dropdown_scroll + i,
                                    max(0, len(preset_names) - 1),
                                )
                                _apply_preset_to_dev("right")
                                break
                        dev_right_dropdown_open = False
                    elif left_depth_rect.collidepoint(mx, my):
                        _focus_field("dev_left_depth")
                        dev_left_dropdown_open = False
                        dev_right_dropdown_open = False
                    elif right_depth_rect.collidepoint(mx, my):
                        _focus_field("dev_right_depth")
                        dev_left_dropdown_open = False
                        dev_right_dropdown_open = False
                    elif any(r.collidepoint(mx, my) for r in left_field_rects.values()):
                        for k, r in left_field_rects.items():
                            if r.collidepoint(mx, my):
                                if k in bool_cfg_keys:
                                    cur = dev_left_cfg_fields.get(k, "false").strip().lower()
                                    dev_left_cfg_fields[k] = "false" if cur in ("true", "1", "yes", "y") else "true"
                                    active_text_field = None
                                    bool_flash_until_ms[f"dev_left_{k}"] = pygame.time.get_ticks() + 250
                                else:
                                    _focus_field(f"dev_left_{k}")
                                break
                        dev_left_dropdown_open = False
                        dev_right_dropdown_open = False
                    elif any(r.collidepoint(mx, my) for r in right_field_rects.values()):
                        for k, r in right_field_rects.items():
                            if r.collidepoint(mx, my):
                                if k in bool_cfg_keys:
                                    cur = dev_right_cfg_fields.get(k, "false").strip().lower()
                                    dev_right_cfg_fields[k] = "false" if cur in ("true", "1", "yes", "y") else "true"
                                    active_text_field = None
                                    bool_flash_until_ms[f"dev_right_{k}"] = pygame.time.get_ticks() + 250
                                else:
                                    _focus_field(f"dev_right_{k}")
                                break
                        dev_left_dropdown_open = False
                        dev_right_dropdown_open = False
                    elif start_rect.collidepoint(mx, my):
                        _start_dev_mode_from_modal()
                        dev_left_dropdown_open = False
                        dev_right_dropdown_open = False
                    else:
                        active_text_field = None
                        dev_left_dropdown_open = False
                        dev_right_dropdown_open = False
                    continue

                if active_modal == "custom_ai":
                    panel_rect = pygame.Rect(140, 90, Window_size[0] - 280, Window_size[1] - 180)
                    if modal_close_button_rect(panel_rect).collidepoint(mx, my):
                        _close_modal_and_refresh()
                        custom_dropdown_open = False
                        continue
                    if not panel_rect.collidepoint(mx, my):
                        _close_modal_and_refresh()
                        custom_dropdown_open = False
                        continue
                    preset_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 70, panel_rect.width - 60, 32)
                    depth_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 122, 140, 30)
                    start_rect = pygame.Rect(panel_rect.centerx - 80, panel_rect.bottom - 60, 160, 38)
                    cfg_keys = [
                        "use_cython_search",
                        "use_tss",
                        "use_lazy_smp",
                        "beam_width_root",
                        "beam_width_inner",
                        "move_time_budget_sec",
                    ]
                    bool_cfg_keys = {"use_cython_search", "use_tss", "use_lazy_smp"}
                    field_rects = {
                        key: pygame.Rect(panel_rect.x + 30 + (i % 2) * ((panel_rect.width - 90) // 2 + 30),
                                         panel_rect.y + 180 + (i // 2) * 44,
                                         (panel_rect.width - 90) // 2,
                                         30)
                        for i, key in enumerate(cfg_keys)
                    }
                    dropdown_rects = [
                        pygame.Rect(preset_rect.x, preset_rect.bottom + i * 28, preset_rect.width, 28)
                        for i in range(min(len(preset_names), dev_dropdown_visible_rows))
                    ]
                    if preset_rect.collidepoint(mx, my):
                        custom_dropdown_open = not custom_dropdown_open
                    elif custom_dropdown_open and any(r.collidepoint(mx, my) for r in dropdown_rects):
                        for i, r in enumerate(dropdown_rects):
                            if r.collidepoint(mx, my):
                                custom_preset_idx = min(
                                    custom_dropdown_scroll + i,
                                    max(0, len(preset_names) - 1),
                                )
                                _apply_preset_to_custom()
                                break
                        custom_dropdown_open = False
                    elif depth_rect.collidepoint(mx, my):
                        _focus_field("custom_depth")
                        custom_dropdown_open = False
                    elif any(r.collidepoint(mx, my) for r in field_rects.values()):
                        for k, r in field_rects.items():
                            if r.collidepoint(mx, my):
                                if k in bool_cfg_keys:
                                    cur = custom_cfg_fields.get(k, "false").strip().lower()
                                    custom_cfg_fields[k] = "false" if cur in ("true", "1", "yes", "y") else "true"
                                    active_text_field = None
                                    bool_flash_until_ms[f"custom_{k}"] = pygame.time.get_ticks() + 250
                                else:
                                    _focus_field(f"custom_{k}")
                                break
                        custom_dropdown_open = False
                    elif start_rect.collidepoint(mx, my):
                        _start_custom_mode_from_modal()
                        custom_dropdown_open = False
                    else:
                        active_text_field = None
                        custom_dropdown_open = False
                    continue

                if active_modal == "benchmark":
                    panel_rect = pygame.Rect(90, 80, Window_size[0] - 180, Window_size[1] - 160)
                    if modal_close_button_rect(panel_rect).collidepoint(mx, my):
                        _close_modal_and_refresh()
                        continue
                    if not panel_rect.collidepoint(mx, my):
                        _close_modal_and_refresh()
                        continue
                    path_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 70, panel_rect.width - 220, 34)
                    browse_rect = pygame.Rect(path_rect.right + 10, path_rect.y, 120, 34)
                    workers_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 125, 140, 34)
                    create_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 175, 320, 36)
                    guide_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 225, 320, 36)
                    start_rect = pygame.Rect(panel_rect.centerx - 80, panel_rect.bottom - 60, 160, 38)

                    if path_rect.collidepoint(mx, my):
                        _focus_field("benchmark_path")
                    elif workers_rect.collidepoint(mx, my):
                        _focus_field("benchmark_workers")
                    elif browse_rect.collidepoint(mx, my):
                        # Release any pygame input grab before native file dialog.
                        was_grabbed = pygame.event.get_grab()
                        pygame.event.set_grab(False)
                        pygame.mouse.set_visible(True)
                        selected = menu_overlay.browse_json_file(menu_overlay.default_desktop_dir())
                        if was_grabbed:
                            pygame.event.set_grab(True)
                        pygame.event.pump()
                        if selected:
                            benchmark_path_input = selected
                    elif create_rect.collidepoint(mx, my):
                        dst = _resolve_benchmark_cfg_path(benchmark_path_input)
                        try:
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            with open(benchmark_cfg_default_file, "r", encoding="utf-8") as sf, open(dst, "w", encoding="utf-8") as df:
                                df.write(sf.read())
                            modal_message = f"Sample config overwritten: {dst}"
                        except Exception as ex:
                            modal_message = f"Create sample failed: {ex}"
                    elif guide_rect.collidepoint(mx, my):
                        active_modal = "benchmark_guide"
                    elif start_rect.collidepoint(mx, my):
                        _start_benchmark_mode()
                    else:
                        active_text_field = None
                    continue

                if active_modal == "error":
                    panel_rect = pygame.Rect(140, 120, Window_size[0] - 280, Window_size[1] - 240)
                    if modal_close_button_rect(panel_rect).collidepoint(mx, my) or not panel_rect.collidepoint(mx, my):
                        active_modal = error_modal_return_to
                        active_text_field = None
                        _refresh_full_screen_after_mode_switch()
                        continue

            if event.type == pygame.MOUSEWHEEL and active_modal == "dev":
                panel_rect = pygame.Rect(80, 70, Window_size[0] - 160, Window_size[1] - 140)
                left_preset_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 70, 300, 30)
                right_preset_rect = pygame.Rect(panel_rect.centerx + 20, panel_rect.y + 70, 300, 30)
                left_list_rect = pygame.Rect(
                    left_preset_rect.x,
                    left_preset_rect.bottom,
                    left_preset_rect.width,
                    28 * min(len(preset_names), dev_dropdown_visible_rows),
                )
                right_list_rect = pygame.Rect(
                    right_preset_rect.x,
                    right_preset_rect.bottom,
                    right_preset_rect.width,
                    28 * min(len(preset_names), dev_dropdown_visible_rows),
                )
                mx, my = pygame.mouse.get_pos()
                max_scroll = max(0, len(preset_names) - dev_dropdown_visible_rows)
                if dev_left_dropdown_open and left_list_rect.collidepoint(mx, my):
                    dev_left_dropdown_scroll = min(max(0, dev_left_dropdown_scroll - event.y), max_scroll)
                    continue
                if dev_right_dropdown_open and right_list_rect.collidepoint(mx, my):
                    dev_right_dropdown_scroll = min(max(0, dev_right_dropdown_scroll - event.y), max_scroll)
                    continue
            if event.type == pygame.MOUSEWHEEL and active_modal == "custom_ai":
                panel_rect = pygame.Rect(140, 90, Window_size[0] - 280, Window_size[1] - 180)
                preset_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 70, panel_rect.width - 60, 32)
                list_rect = pygame.Rect(
                    preset_rect.x,
                    preset_rect.bottom,
                    preset_rect.width,
                    28 * min(len(preset_names), dev_dropdown_visible_rows),
                )
                mx, my = pygame.mouse.get_pos()
                max_scroll = max(0, len(preset_names) - dev_dropdown_visible_rows)
                if custom_dropdown_open and list_rect.collidepoint(mx, my):
                    custom_dropdown_scroll = min(max(0, custom_dropdown_scroll - event.y), max_scroll)
                    continue

            if event.type == pygame.KEYDOWN and active_text_field:
                target = None
                if active_text_field == "dev_left_depth":
                    target = "dev_left_depth"
                elif active_text_field == "dev_right_depth":
                    target = "dev_right_depth"
                elif active_text_field == "benchmark_path":
                    target = "benchmark_path"
                elif active_text_field == "benchmark_workers":
                    target = "benchmark_workers"
                elif active_text_field == "custom_depth":
                    target = "custom_depth"
                elif active_text_field.startswith("dev_left_"):
                    target = active_text_field
                elif active_text_field.startswith("dev_right_"):
                    target = active_text_field
                elif active_text_field.startswith("custom_"):
                    target = active_text_field
                if target is not None:
                    cur_val = _get_field_value(target)
                    cur_pos = max(0, min(cursor_pos_by_field.get(target, len(cur_val)), len(cur_val)))
                    if event.key == pygame.K_LEFT:
                        cursor_pos_by_field[target] = max(0, cur_pos - 1)
                    elif event.key == pygame.K_RIGHT:
                        cursor_pos_by_field[target] = min(len(cur_val), cur_pos + 1)
                    elif event.key == pygame.K_HOME:
                        cursor_pos_by_field[target] = 0
                    elif event.key == pygame.K_END:
                        cursor_pos_by_field[target] = len(cur_val)
                    elif event.key == pygame.K_BACKSPACE:
                        if cur_pos > 0:
                            new_val = cur_val[:cur_pos - 1] + cur_val[cur_pos:]
                            _set_field_value(target, new_val)
                            cursor_pos_by_field[target] = cur_pos - 1
                    elif event.key == pygame.K_DELETE:
                        if cur_pos < len(cur_val):
                            new_val = cur_val[:cur_pos] + cur_val[cur_pos + 1:]
                            _set_field_value(target, new_val)
                            cursor_pos_by_field[target] = cur_pos
                    elif event.key == pygame.K_RETURN:
                        active_text_field = None
                    elif event.unicode:
                        ch = event.unicode
                        allow_text = target == "benchmark_path"
                        allow_digit = target != "benchmark_path"
                        if (allow_text and ch.isprintable() and ch != "\r" and ch != "\n") or (allow_digit and ch.isdigit()):
                            new_val = cur_val[:cur_pos] + ch + cur_val[cur_pos:]
                            _set_field_value(target, new_val)
                            cursor_pos_by_field[target] = cur_pos + 1
                continue

            if active_modal is not None:
                if event.type == pygame.QUIT:
                    done = True
                if event.type == pygame.VIDEORESIZE:
                    update_layout(event.w, event.h)
                if event.type == pygame.WINDOWSIZECHANGED:
                    current_w, current_h = pygame.display.get_window_size()
                    update_layout(current_w, current_h)
                continue
            _bench_multi_skip_panel_btns = (
                game_mode is GameMode.BENCHMARK
                and benchmark_state.get('parallel_workers', 1) > 1
            )

    # ---------------- Undo button ---------------------------------------------
            if not _bench_multi_skip_panel_btns and undo_button.draw(Screen):  # Ấn nút Undo
                if game_mode is GameMode.BENCHMARK:
                    continue
                if ai_future is not None:
                    ai_future.cancel()
                    ai_future = None
                if dev_future is not None:
                    dev_future.cancel()
                    dev_future = None
                ai_is_thinking = False
                ai_thinking_btn.disable_button()
                Undo(my_game)
                if game_mode is GameMode.DEVELOPER:
                    dev_mode_setup['pause'] = True
                    set_turn_timer_pause(True)
                    if dev_future is not None:
                        dev_future.cancel()
                        dev_future = None
                    ai_is_thinking = False
                    ai_thinking_btn.disable_button()
                update_game_status(my_game.get_winner())
                print("Undo")
                pass
    # --------------Exit button--------------------------------------------
            if not _bench_multi_skip_panel_btns and exit_button.draw(Screen):  # Ấn nút Thoát
                print('EXIT')
                done = True
    # --------------Replay button-------------------------------------------
            if not _bench_multi_skip_panel_btns and replay_button.draw(Screen):  # Ấn nút Chơi lại
                if game_mode is GameMode.BENCHMARK:
                    if len(benchmark_setup['matchups']) == 0:
                        print("[BENCH] replay ignored: no matchups configured")
                        continue
                    if dev_future is not None:
                        dev_future.cancel()
                        dev_future = None
                    ai_is_thinking = False
                    ai_thinking_btn.disable_button()
                    if ai_executor is not None:
                        ai_executor.shutdown(wait=False, cancel_futures=True)
                        ai_executor = None
                    if benchmark_state['matchup_idx'] >= len(benchmark_setup['matchups']):
                        benchmark_state['matchup_idx'] = 0
                        benchmark_state['game_idx'] = 0
                    if ai_executor is None:
                        ai_executor = ProcessPoolExecutor(max_workers=1)
                        bench_sess.benchmark_warm_executor(ai_executor, 1)
                    benchmark_setup_game()
                    benchmark_state['running'] = True
                    turn_elapsed_paused = 0.0
                    turn_started_at = time.perf_counter()
                    turn_elapsed_frozen = None
                    set_turn_timer_pause(False)
                    print(
                        f"[BENCH] replay current game: matchup_idx={benchmark_state['matchup_idx']}, "
                        f"game_idx={benchmark_state['game_idx']}"
                    )
                    continue
                print('Replay')
                my_game.reset()
                if ai_future is not None:
                    ai_future.cancel()
                    ai_future = None
                if dev_future is not None:
                    dev_future.cancel()
                    dev_future = None
                ai_is_thinking = False
                ai_thinking_btn.disable_button()
                if game_mode is GameMode.DEVELOPER:
                    dev_mode_setup['pause'] = False
                    set_turn_timer_pause(False)
                turn_started_at = time.perf_counter()
                turn_elapsed_frozen = None
                update_game_status(my_game.get_winner())
                re_draw()
    # --------- Normal PvAI controls (hidden in dev / benchmark) ----------
            if game_mode in (GameMode.NORMAL, GameMode.CUSTOM_AI):
        # ------------- Setup button---------------------------------------------
                if len(my_game.last_move) > 0:
                    pass
                if not my_game.is_use_ai:
                    pass
                else:
                    pass

        # -----------pvp button----------------------------------------------------
                if game_mode is GameMode.NORMAL and pvp_btn.draw(Screen):
                    my_game.use_ai(False)
                    pvp_btn.disable_button()
                    aivp_btn.enable_button()
                    print("P_P")
                    pass
        # ------------ai vs p button------------------------------------------------
                if game_mode is GameMode.NORMAL and aivp_btn.draw(Screen):
                    my_game.use_ai(True)
                    aivp_btn.disable_button()
                    pvp_btn.enable_button()
                    agent = build_player_vs_ai_agent()
                    print("AI_P")
                    pass
        # --------------Draw ai thinking button ------------------------------------
                if ai_thinking_btn.draw(Screen):
                    pass
        # ----------hard button-----------------------------------------------------
                if game_mode is GameMode.NORMAL and h_btn.draw(Screen):
                    h_btn.disable_button()
                    m_btn.enable_button()
                    e_btn.enable_button()
                    grand_master_btn.enable_button()
                    normal_mode_difficulty = 'hard'
                    my_game.change_hard_ai("hard")
                    agent = build_player_vs_ai_agent()
                    print("Hard")
                    pass
        # ----------medium button---------------------------------------------------
                if game_mode is GameMode.NORMAL and m_btn.draw(Screen):
                    h_btn.enable_button()
                    m_btn.disable_button()
                    e_btn.enable_button()
                    grand_master_btn.enable_button()
                    normal_mode_difficulty = 'medium'
                    my_game.change_hard_ai("medium")
                    agent = build_player_vs_ai_agent()
                    print("Medium")
                    pass
        # -------------easy button--------------------------------------------------
                if game_mode is GameMode.NORMAL and e_btn.draw(Screen):
                    h_btn.enable_button()
                    m_btn.enable_button()
                    e_btn.disable_button()
                    grand_master_btn.enable_button()
                    normal_mode_difficulty = 'easy'
                    my_game.change_hard_ai("easy")
                    agent = build_player_vs_ai_agent()
                    print("Easy")
                    pass
        # ----------grand master button--------------------------------------------
                if game_mode is GameMode.NORMAL and grand_master_btn.draw(Screen):
                    h_btn.enable_button()
                    m_btn.enable_button()
                    e_btn.enable_button()
                    grand_master_btn.disable_button()
                    normal_mode_difficulty = 'grand_master'
                    my_game.change_hard_ai("hard")
                    agent = build_player_vs_ai_agent()
                    print("Grand Master")
                    pass
        # -------Choose person play first button------------------------------------
                if person_btn.draw(Screen):  # Ấn nút Chọn người đi trước
                    person_btn.disable_button()
                    ai_btn.enable_button()
                    my_game.set_ai_turn(2)
                    agent = build_custom_ai_agent(custom_ai_setup) if game_mode is GameMode.CUSTOM_AI else build_player_vs_ai_agent()
                    print("Human")
                    pass
        # -------Choose AI play first button------------------------------------
                if ai_btn.draw(Screen):  # Ấn nút Chọn AI đi trước
                    ai_btn.disable_button()
                    person_btn.enable_button()
                    my_game.set_ai_turn(1)
                    agent = build_custom_ai_agent(custom_ai_setup) if game_mode is GameMode.CUSTOM_AI else build_player_vs_ai_agent()
                    print("AI")
                    pass

        # -----------------checking is exit game? ------------------------------
                if event.type == pygame.QUIT:  # If user clicked close
                    done = True  # Flag that we are done so we exit this loop
                    # Set the screen background
                if event.type == pygame.VIDEORESIZE:
                    update_layout(event.w, event.h)
                if event.type == pygame.WINDOWSIZECHANGED:
                    current_w, current_h = pygame.display.get_window_size()
                    update_layout(current_w, current_h)
        # -------Find pos mouse clicked and make a move-------------------------
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if game_mode is GameMode.BENCHMARK:
                        continue
                    if my_game.is_use_ai and (my_game.turn == my_game.ai_turn or ai_is_thinking):
                        continue
                    pos = pygame.mouse.get_pos()
                    local_x = pos[0] - BOARD_OFFSET_X
                    local_y = pos[1] - BOARD_OFFSET_Y
                    col = int(local_x // (WIDTH + MARGIN))
                    row = int(local_y // (HEIGHT + MARGIN))
                    # print(pos, col, row)
                    if 0 <= col < COLNUM and 0 <= row < ROWNUM:
                        apply_move_with_timer(my_game, row, col, actor="player")
                    update_game_status(my_game.get_winner())
                    if my_game.is_use_ai and my_game.turn == my_game.ai_turn:
                        ai_thinking_btn.enable_button()
                        ai_thinking_btn.re_draw(Screen)
                        draw(my_game, Screen)
            else:
                if event.type == pygame.QUIT:
                    done = True
                if event.type == pygame.VIDEORESIZE:
                    update_layout(event.w, event.h)
                if event.type == pygame.WINDOWSIZECHANGED:
                    current_w, current_h = pygame.display.get_window_size()
                    update_layout(current_w, current_h)
                if game_mode is GameMode.BENCHMARK and benchmark_state.get('parallel_workers', 1) <= 1:
                    if start_button.draw(Screen):
                        can_resume_current = (
                            benchmark_state['current'] is not None
                            and benchmark_state['matchup_idx'] < len(benchmark_setup['matchups'])
                            and status == -1
                            and benchmark_state['game_ended_at'] is None
                        )
                        if can_resume_current:
                            if ai_executor is None:
                                ai_executor = ProcessPoolExecutor(max_workers=1)
                                bench_sess.benchmark_warm_executor(ai_executor, 1)
                            benchmark_state['running'] = True
                            turn_elapsed_paused = 0.0
                            turn_started_at = time.perf_counter()
                            set_turn_timer_pause(False)
                            print("[BENCH] resumed current game")
                        else:
                            if ai_executor is None:
                                ai_executor = ProcessPoolExecutor(max_workers=1)
                                bench_sess.benchmark_warm_executor(ai_executor, 1)
                            benchmark_state['matchup_idx'] = benchmark_state.get('resume_matchup_idx', 0)
                            benchmark_state['game_idx'] = benchmark_state.get('resume_game_idx', 0)
                            benchmark_state['stats'] = {}
                            benchmark_state['results'] = []
                            benchmark_setup_game()
                            benchmark_state['running'] = True
                            turn_started_at = time.perf_counter()
                            turn_elapsed_frozen = None
                            set_turn_timer_pause(False)
                            print("[BENCH] benchmark mode started")
                    if pause_button.draw(Screen):
                        if benchmark_state['running']:
                            benchmark_state['running'] = False
                            set_turn_timer_pause(True)
                            if dev_future is not None:
                                dev_future.cancel()
                                dev_future = None
                            if ai_executor is not None:
                                ai_executor.shutdown(wait=False, cancel_futures=True)
                                ai_executor = None
                            ai_is_thinking = False
                            ai_thinking_btn.disable_button()
                            print("[BENCH] paused (agent computation hard-stopped)")
                elif game_mode is GameMode.DEVELOPER:
                    if start_button.draw(Screen):
                        if not dev_mode_setup['start']:
                            turn_started_at = time.perf_counter()
                            turn_elapsed_frozen = None
                        dev_mode_setup['start'] = True
                        dev_mode_setup['pause'] = False
                        set_turn_timer_pause(False)
                        ai_thinking_btn.enable_button()
                    if pause_button.draw(Screen):
                        if dev_mode_setup['start']:
                            dev_mode_setup['pause'] = not dev_mode_setup['pause']
                            set_turn_timer_pause(dev_mode_setup['pause'])
                            if dev_mode_setup['pause']:
                                if dev_future is not None:
                                    dev_future.cancel()
                                    dev_future = None
                                ai_is_thinking = False
                                ai_thinking_btn.disable_button()
                if not (
                    game_mode is GameMode.BENCHMARK
                    and benchmark_state.get('parallel_workers', 1) > 1
                ):
                    ai_thinking_btn.re_draw(Screen)

        # ------ Draw screen---------------------------------------------------
        if game_mode is GameMode.BENCHMARK and benchmark_state.get('parallel_workers', 1) > 1:
            bench_sess.draw_benchmark_multi_screen(
                Screen,
                benchmark_state,
                black=BLACK,
                white=WHITE,
                green=GREEN,
                red=RED,
                blue=BLUE,
            )
            if bench_sess.handle_benchmark_multi_ui_frame(
                Screen,
                benchmark_setup,
                benchmark_state,
                bench_rt,
                start_button=start_button,
                pause_button=pause_button,
                replay_button=replay_button,
                exit_button=exit_button,
            ):
                done = True
        else:
            draw(my_game, Screen)
            if game_mode not in (GameMode.NORMAL, GameMode.CUSTOM_AI) and SHOW_DEV_START_DEBUG_BORDER:
                pygame.draw.rect(Screen, (255, 255, 0), start_button.rect, 3)
                pygame.draw.rect(Screen, (0, 255, 255), pause_button.rect, 3)
            checking_winning(status)
            if game_mode is GameMode.CUSTOM_AI:
                custom_ai_ui.draw_custom_ai_summary(
                    Screen,
                    panel_x=PANEL_X,
                    title_y=198,
                    summary=custom_ai_setup,
                    white=WHITE,
                )

        # Top dropdown menu
        menu_overlay.draw_text_button(Screen, menu_button_rect, "Menu")
        if dropdown_open:
            for item_rect, item in zip(menu_item_rects, menu_items):
                is_normal_item = item == "NormalMode"
                enabled = not (is_normal_item and game_mode is GameMode.NORMAL)
                menu_overlay.draw_text_button(Screen, item_rect, item, enabled=enabled)

        # Modals (draw on top)
        if active_modal in ("help", "about", "benchmark_guide", "dev", "custom_ai", "benchmark", "error"):
            overlay = pygame.Surface((Window_size[0], Window_size[1]), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            Screen.blit(overlay, (0, 0))

        if active_modal == "help":
            panel_rect = pygame.Rect(80, 70, Window_size[0] - 160, Window_size[1] - 140)
            pygame.draw.rect(Screen, (25, 25, 25), panel_rect, border_radius=8)
            pygame.draw.rect(Screen, (180, 180, 180), panel_rect, 1, border_radius=8)
            draw_modal_close_button(Screen, panel_rect)
            max_w = panel_rect.width - 20
            max_h = panel_rect.height - 20
            iw, ih = instructions_img_org.get_size()
            scale = min(max_w / max(1, iw), max_h / max(1, ih))
            img = pygame.transform.smoothscale(instructions_img_org, (max(1, int(iw * scale)), max(1, int(ih * scale))))
            Screen.blit(img, img.get_rect(center=panel_rect.center))

        if active_modal == "about":
            panel_rect = pygame.Rect(80, 70, Window_size[0] - 160, Window_size[1] - 140)
            pygame.draw.rect(Screen, (25, 25, 25), panel_rect, border_radius=8)
            pygame.draw.rect(Screen, (180, 180, 180), panel_rect, 1, border_radius=8)
            draw_modal_close_button(Screen, panel_rect)
            title_font = pygame.font.Font("freesansbold.ttf", 28)
            body_font = pygame.font.Font("freesansbold.ttf", 18)
            Screen.blit(title_font.render("About Caro AI", True, WHITE), (panel_rect.x + 24, panel_rect.y + 20))
            about_lines = [
                "Author: MonHau VD",
                "GitHub: https://github.com/MonHauVD/Caro_AI",
                "Caro AI uses minimax with alpha-beta pruning.",
                "Current version includes presets, benchmark mode,",
                "developer AI-vs-AI mode, and optional acceleration.",
                "Click outside this panel to close.",
            ]
            for i, ln in enumerate(about_lines):
                Screen.blit(body_font.render(ln, True, (220, 220, 220)), (panel_rect.x + 24, panel_rect.y + 75 + i * 28))

        if active_modal == "benchmark_guide":
            panel_rect = pygame.Rect(80, 70, Window_size[0] - 160, Window_size[1] - 140)
            pygame.draw.rect(Screen, (25, 25, 25), panel_rect, border_radius=8)
            pygame.draw.rect(Screen, (180, 180, 180), panel_rect, 1, border_radius=8)
            draw_modal_close_button(Screen, panel_rect)
            title_font = pygame.font.Font("freesansbold.ttf", 24)
            body_font = pygame.font.Font("freesansbold.ttf", 17)
            Screen.blit(title_font.render("Benchmark Config Guide", True, WHITE), (panel_rect.x + 20, panel_rect.y + 16))
            guide_lines = [
                "1) games_per_matchup: number of games for each pairing.",
                "2) custom_agents: reusable agent presets (depth + config).",
                "3) matchups: list each battle with agent_a and agent_b.",
                "4) For each agent: set label, depth and config fields.",
                "5) output_dir controls where result files are written.",
                "6) Save JSON, then click Start Benchmark.",
                "Click outside to close.",
            ]
            for i, ln in enumerate(guide_lines):
                Screen.blit(body_font.render(ln, True, (225, 225, 225)), (panel_rect.x + 20, panel_rect.y + 62 + i * 30))

        if active_modal == "dev":
            panel_rect = pygame.Rect(80, 70, Window_size[0] - 160, Window_size[1] - 140)
            pygame.draw.rect(Screen, (22, 22, 22), panel_rect, border_radius=8)
            pygame.draw.rect(Screen, (180, 180, 180), panel_rect, 1, border_radius=8)
            draw_modal_close_button(Screen, panel_rect)
            title_font = pygame.font.Font("freesansbold.ttf", 24)
            label_font = pygame.font.Font("freesansbold.ttf", 16)
            caret_visible = (pygame.time.get_ticks() // 500) % 2 == 0
            Screen.blit(title_font.render("DevMode setup (AI vs AI)", True, WHITE), (panel_rect.x + 20, panel_rect.y + 16))
            left_preset_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 70, 300, 30)
            right_preset_rect = pygame.Rect(panel_rect.centerx + 20, panel_rect.y + 70, 300, 30)
            left_depth_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 120, 130, 30)
            right_depth_rect = pygame.Rect(panel_rect.centerx + 20, panel_rect.y + 120, 130, 30)
            cfg_keys = [
                "use_cython_search",
                "use_tss",
                "use_lazy_smp",
                "beam_width_root",
                "beam_width_inner",
                "move_time_budget_sec",
            ]
            left_field_rects = {
                key: pygame.Rect(panel_rect.x + 30, panel_rect.y + 170 + i * 42, panel_rect.width // 2 - 70, 30)
                for i, key in enumerate(cfg_keys)
            }
            right_field_rects = {
                key: pygame.Rect(panel_rect.centerx + 20, panel_rect.y + 170 + i * 42, panel_rect.width // 2 - 70, 30)
                for i, key in enumerate(cfg_keys)
            }
            start_rect = pygame.Rect(panel_rect.centerx - 70, panel_rect.bottom - 60, 140, 36)
            Screen.blit(label_font.render("Left AI preset (dropdown)", True, WHITE), (left_preset_rect.x, left_preset_rect.y - 20))
            Screen.blit(label_font.render("Right AI preset (dropdown)", True, WHITE), (right_preset_rect.x, right_preset_rect.y - 20))
            menu_overlay.draw_text_button(Screen, left_preset_rect, preset_names[dev_left_preset_idx], selected=dev_left_dropdown_open)
            menu_overlay.draw_text_button(Screen, right_preset_rect, preset_names[dev_right_preset_idx], selected=dev_right_dropdown_open)
            pygame.draw.rect(Screen, (44, 44, 44), left_depth_rect, border_radius=4)
            pygame.draw.rect(Screen, (44, 44, 44), right_depth_rect, border_radius=4)
            left_depth_active = active_text_field == "dev_left_depth"
            right_depth_active = active_text_field == "dev_right_depth"
            if left_depth_active:
                pygame.draw.rect(Screen, (95, 170, 255), left_depth_rect, 2, border_radius=4)
            if right_depth_active:
                pygame.draw.rect(Screen, (95, 170, 255), right_depth_rect, 2, border_radius=4)
            Screen.blit(label_font.render("Depth", True, WHITE), (left_depth_rect.x, left_depth_rect.y - 18))
            Screen.blit(label_font.render("Depth", True, WHITE), (right_depth_rect.x, right_depth_rect.y - 18))
            Screen.blit(label_font.render(dev_left_depth, True, WHITE), (left_depth_rect.x + 8, left_depth_rect.y + 8))
            Screen.blit(label_font.render(dev_right_depth, True, WHITE), (right_depth_rect.x + 8, right_depth_rect.y + 8))
            if left_depth_active and caret_visible:
                cur = max(0, min(cursor_pos_by_field.get("dev_left_depth", len(dev_left_depth)), len(dev_left_depth)))
                cx = left_depth_rect.x + 8 + label_font.size(dev_left_depth[:cur])[0] + 1
                pygame.draw.line(Screen, WHITE, (cx, left_depth_rect.y + 6), (cx, left_depth_rect.y + left_depth_rect.height - 6), 2)
            if right_depth_active and caret_visible:
                cur = max(0, min(cursor_pos_by_field.get("dev_right_depth", len(dev_right_depth)), len(dev_right_depth)))
                cx = right_depth_rect.x + 8 + label_font.size(dev_right_depth[:cur])[0] + 1
                pygame.draw.line(Screen, WHITE, (cx, right_depth_rect.y + 6), (cx, right_depth_rect.y + right_depth_rect.height - 6), 2)
            for key in cfg_keys:
                lrect = left_field_rects[key]
                rrect = right_field_rects[key]
                pygame.draw.rect(Screen, (44, 44, 44), lrect, border_radius=4)
                pygame.draw.rect(Screen, (44, 44, 44), rrect, border_radius=4)
                Screen.blit(label_font.render(key, True, (205, 205, 205)), (lrect.x, lrect.y - 16))
                Screen.blit(label_font.render(key, True, (205, 205, 205)), (rrect.x, rrect.y - 16))
                left_val = dev_left_cfg_fields.get(key, "")
                right_val = dev_right_cfg_fields.get(key, "")
                Screen.blit(label_font.render(left_val, True, WHITE), (lrect.x + 8, lrect.y + 7))
                Screen.blit(label_font.render(right_val, True, WHITE), (rrect.x + 8, rrect.y + 7))
                left_key_active = active_text_field == f"dev_left_{key}"
                right_key_active = active_text_field == f"dev_right_{key}"
                left_bool_flash = bool_flash_until_ms.get(f"dev_left_{key}", 0) > pygame.time.get_ticks()
                right_bool_flash = bool_flash_until_ms.get(f"dev_right_{key}", 0) > pygame.time.get_ticks()
                if left_key_active:
                    pygame.draw.rect(Screen, (95, 170, 255), lrect, 2, border_radius=4)
                elif key in ("use_cython_search", "use_tss", "use_lazy_smp") and left_bool_flash:
                    pygame.draw.rect(Screen, (95, 170, 255), lrect, 2, border_radius=4)
                if right_key_active:
                    pygame.draw.rect(Screen, (95, 170, 255), rrect, 2, border_radius=4)
                elif key in ("use_cython_search", "use_tss", "use_lazy_smp") and right_bool_flash:
                    pygame.draw.rect(Screen, (95, 170, 255), rrect, 2, border_radius=4)
                if left_key_active and caret_visible:
                    cur = max(0, min(cursor_pos_by_field.get(f"dev_left_{key}", len(left_val)), len(left_val)))
                    cx = lrect.x + 8 + label_font.size(left_val[:cur])[0] + 1
                    pygame.draw.line(Screen, WHITE, (cx, lrect.y + 6), (cx, lrect.y + lrect.height - 6), 2)
                if right_key_active and caret_visible:
                    cur = max(0, min(cursor_pos_by_field.get(f"dev_right_{key}", len(right_val)), len(right_val)))
                    cx = rrect.x + 8 + label_font.size(right_val[:cur])[0] + 1
                    pygame.draw.line(Screen, WHITE, (cx, rrect.y + 6), (cx, rrect.y + rrect.height - 6), 2)
            if dev_left_dropdown_open:
                left_start = min(max(0, dev_left_dropdown_scroll), max(0, len(preset_names) - dev_dropdown_visible_rows))
                left_slice = preset_names[left_start:left_start + dev_dropdown_visible_rows]
                for i, name in enumerate(left_slice):
                    r = pygame.Rect(left_preset_rect.x, left_preset_rect.bottom + i * 28, left_preset_rect.width, 28)
                    menu_overlay.draw_text_button(
                        Screen,
                        r,
                        name,
                        selected=(left_start + i == dev_left_preset_idx),
                    )
            if dev_right_dropdown_open:
                right_start = min(max(0, dev_right_dropdown_scroll), max(0, len(preset_names) - dev_dropdown_visible_rows))
                right_slice = preset_names[right_start:right_start + dev_dropdown_visible_rows]
                for i, name in enumerate(right_slice):
                    r = pygame.Rect(right_preset_rect.x, right_preset_rect.bottom + i * 28, right_preset_rect.width, 28)
                    menu_overlay.draw_text_button(
                        Screen,
                        r,
                        name,
                        selected=(right_start + i == dev_right_preset_idx),
                    )
            menu_overlay.draw_text_button(Screen, start_rect, "Start Dev")

        if active_modal == "custom_ai":
            panel_rect = pygame.Rect(140, 90, Window_size[0] - 280, Window_size[1] - 180)
            pygame.draw.rect(Screen, (22, 22, 22), panel_rect, border_radius=8)
            pygame.draw.rect(Screen, (180, 180, 180), panel_rect, 1, border_radius=8)
            draw_modal_close_button(Screen, panel_rect)
            title_font = pygame.font.Font("freesansbold.ttf", 24)
            label_font = pygame.font.Font("freesansbold.ttf", 16)
            caret_visible = (pygame.time.get_ticks() // 500) % 2 == 0
            Screen.blit(title_font.render("Custom AI setup", True, WHITE), (panel_rect.x + 20, panel_rect.y + 16))
            preset_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 70, panel_rect.width - 60, 32)
            depth_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 122, 140, 30)
            start_rect = pygame.Rect(panel_rect.centerx - 80, panel_rect.bottom - 60, 160, 38)
            cfg_keys = [
                "use_cython_search",
                "use_tss",
                "use_lazy_smp",
                "beam_width_root",
                "beam_width_inner",
                "move_time_budget_sec",
            ]
            field_rects = {
                key: pygame.Rect(panel_rect.x + 30 + (i % 2) * ((panel_rect.width - 90) // 2 + 30),
                                 panel_rect.y + 180 + (i // 2) * 44,
                                 (panel_rect.width - 90) // 2,
                                 30)
                for i, key in enumerate(cfg_keys)
            }
            Screen.blit(label_font.render("Preset (dropdown)", True, WHITE), (preset_rect.x, preset_rect.y - 20))
            menu_overlay.draw_text_button(Screen, preset_rect, preset_names[custom_preset_idx], selected=custom_dropdown_open)
            pygame.draw.rect(Screen, (44, 44, 44), depth_rect, border_radius=4)
            if active_text_field == "custom_depth":
                pygame.draw.rect(Screen, (95, 170, 255), depth_rect, 2, border_radius=4)
            Screen.blit(label_font.render("Depth", True, WHITE), (depth_rect.x, depth_rect.y - 18))
            Screen.blit(label_font.render(custom_depth, True, WHITE), (depth_rect.x + 8, depth_rect.y + 7))
            if active_text_field == "custom_depth" and caret_visible:
                cur = max(0, min(cursor_pos_by_field.get("custom_depth", len(custom_depth)), len(custom_depth)))
                cx = depth_rect.x + 8 + label_font.size(custom_depth[:cur])[0] + 1
                pygame.draw.line(Screen, WHITE, (cx, depth_rect.y + 6), (cx, depth_rect.y + depth_rect.height - 6), 2)
            for key in cfg_keys:
                rect = field_rects[key]
                val = custom_cfg_fields.get(key, "")
                pygame.draw.rect(Screen, (44, 44, 44), rect, border_radius=4)
                if active_text_field == f"custom_{key}":
                    pygame.draw.rect(Screen, (95, 170, 255), rect, 2, border_radius=4)
                elif key in ("use_cython_search", "use_tss", "use_lazy_smp") and bool_flash_until_ms.get(f"custom_{key}", 0) > pygame.time.get_ticks():
                    pygame.draw.rect(Screen, (95, 170, 255), rect, 2, border_radius=4)
                Screen.blit(label_font.render(key, True, (205, 205, 205)), (rect.x, rect.y - 16))
                Screen.blit(label_font.render(val, True, WHITE), (rect.x + 8, rect.y + 7))
                if active_text_field == f"custom_{key}" and caret_visible:
                    cur = max(0, min(cursor_pos_by_field.get(f"custom_{key}", len(val)), len(val)))
                    cx = rect.x + 8 + label_font.size(val[:cur])[0] + 1
                    pygame.draw.line(Screen, WHITE, (cx, rect.y + 6), (cx, rect.y + rect.height - 6), 2)
            if custom_dropdown_open:
                start = min(max(0, custom_dropdown_scroll), max(0, len(preset_names) - dev_dropdown_visible_rows))
                for i, name in enumerate(preset_names[start:start + dev_dropdown_visible_rows]):
                    r = pygame.Rect(preset_rect.x, preset_rect.bottom + i * 28, preset_rect.width, 28)
                    menu_overlay.draw_text_button(Screen, r, name, selected=(start + i == custom_preset_idx))
            menu_overlay.draw_text_button(Screen, start_rect, "Start Custom AI")

        if active_modal == "benchmark":
            panel_rect = pygame.Rect(90, 80, Window_size[0] - 180, Window_size[1] - 160)
            pygame.draw.rect(Screen, (22, 22, 22), panel_rect, border_radius=8)
            pygame.draw.rect(Screen, (180, 180, 180), panel_rect, 1, border_radius=8)
            draw_modal_close_button(Screen, panel_rect)
            title_font = pygame.font.Font("freesansbold.ttf", 24)
            label_font = pygame.font.Font("freesansbold.ttf", 16)
            caret_visible = (pygame.time.get_ticks() // 500) % 2 == 0
            Screen.blit(title_font.render("BenchmarkMode setup", True, WHITE), (panel_rect.x + 20, panel_rect.y + 18))
            path_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 70, panel_rect.width - 220, 34)
            browse_rect = pygame.Rect(path_rect.right + 10, path_rect.y, 120, 34)
            workers_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 125, 140, 34)
            create_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 175, 320, 36)
            guide_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 225, 320, 36)
            start_rect = pygame.Rect(panel_rect.centerx - 80, panel_rect.bottom - 60, 160, 38)
            Screen.blit(label_font.render("Config path (default Desktop)", True, WHITE), (path_rect.x, path_rect.y - 20))
            pygame.draw.rect(Screen, (44, 44, 44), path_rect, border_radius=4)
            if active_text_field == "benchmark_path":
                pygame.draw.rect(Screen, (95, 170, 255), path_rect, 2, border_radius=4)
            Screen.blit(label_font.render(benchmark_path_input[:85], True, (230, 230, 230)), (path_rect.x + 8, path_rect.y + 8))
            if active_text_field == "benchmark_path" and caret_visible:
                view_val = benchmark_path_input[:85]
                cur = max(0, min(cursor_pos_by_field.get("benchmark_path", len(benchmark_path_input)), len(benchmark_path_input)))
                cur = min(cur, len(view_val))
                cx = path_rect.x + 8 + label_font.size(view_val[:cur])[0] + 1
                pygame.draw.line(Screen, WHITE, (cx, path_rect.y + 6), (cx, path_rect.y + path_rect.height - 6), 2)
            Screen.blit(label_font.render("Workers (1..32)", True, WHITE), (workers_rect.x, workers_rect.y - 20))
            pygame.draw.rect(Screen, (44, 44, 44), workers_rect, border_radius=4)
            if active_text_field == "benchmark_workers":
                pygame.draw.rect(Screen, (95, 170, 255), workers_rect, 2, border_radius=4)
            Screen.blit(label_font.render(benchmark_workers_input, True, (230, 230, 230)), (workers_rect.x + 8, workers_rect.y + 8))
            if active_text_field == "benchmark_workers" and caret_visible:
                cur = max(0, min(cursor_pos_by_field.get("benchmark_workers", len(benchmark_workers_input)), len(benchmark_workers_input)))
                cx = workers_rect.x + 8 + label_font.size(benchmark_workers_input[:cur])[0] + 1
                pygame.draw.line(Screen, WHITE, (cx, workers_rect.y + 6), (cx, workers_rect.y + workers_rect.height - 6), 2)
            menu_overlay.draw_text_button(Screen, browse_rect, "Browse")
            menu_overlay.draw_text_button(Screen, create_rect, "Create sample config file")
            menu_overlay.draw_text_button(Screen, guide_rect, "Config editing guide")
            menu_overlay.draw_text_button(Screen, start_rect, "Start Benchmark")
            if modal_message:
                msg_color = (240, 90, 90) if modal_message_is_error else (235, 205, 120)
                Screen.blit(label_font.render(modal_message[:110], True, msg_color), (panel_rect.x + 30, panel_rect.bottom - 92))

        if active_modal == "error":
            panel_rect = pygame.Rect(140, 120, Window_size[0] - 280, Window_size[1] - 240)
            pygame.draw.rect(Screen, (30, 24, 24), panel_rect, border_radius=8)
            pygame.draw.rect(Screen, (200, 120, 120), panel_rect, 1, border_radius=8)
            draw_modal_close_button(Screen, panel_rect)
            title_font = pygame.font.Font("freesansbold.ttf", 24)
            body_font = pygame.font.Font("freesansbold.ttf", 16)
            Screen.blit(title_font.render("Error", True, (255, 150, 150)), (panel_rect.x + 20, panel_rect.y + 16))
            lines = error_modal_message.split("\n")
            for i, ln in enumerate(lines[:8]):
                Screen.blit(body_font.render(ln[:110], True, (240, 220, 220)), (panel_rect.x + 20, panel_rect.y + 58 + i * 24))
            Screen.blit(body_font.render("Close to return Benchmark setup.", True, (215, 215, 215)), (panel_rect.x + 20, panel_rect.bottom - 30))
        # Limit to 999999999 frames per second
        clock.tick(FPS)

        # Go ahead and update the screen with what we've drawn.
        pygame.display.update()

    if game_mode is GameMode.BENCHMARK and benchmark_state.get('initialized'):
        try:
            if bench_sess.export_benchmark_fragments_if_any(
                BENCHMARK_RESULT_SUMMARY_FILE,
                BENCHMARK_RESULT_BOARD_FILE,
                BENCHMARK_RESULT_MOVES_FILE,
                BENCHMARK_FRAGMENTS_DIR,
            ):
                print("[BENCH] đã gộp fragments → 3 file master khi thoát vòng lặp (Exit / hết phiên)")
        except Exception as ex:
            print(f"[BENCH] gộp fragments khi thoát thất bại: {ex}", file=sys.stderr)

    pygame.time.delay(50)
    if ai_executor is not None:
        ai_executor.shutdown(wait=False, cancel_futures=True)
    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()