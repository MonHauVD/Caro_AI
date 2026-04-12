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
from caro_ai.ui import layout as ui_layout
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
    'medium': {
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
    'hard': {
        'depth': 8,
        'config': {
            'use_cython_search': True,
            'cython_search_min_depth': 5,
            'use_tss': False,
            'use_lazy_smp': False,
            'beam_width_root': 10,
            'beam_width_inner': 8,
            'move_time_budget_sec': 20,
        },
    },
}

# Độ khó AI lúc mở app — chỉ chỉnh giá trị tại đây ('easy' | 'medium' | 'hard').
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


def init_application():
    global my_game, agent, agent1, agent2
    global Window_size, BOARD_OFFSET_X, BOARD_OFFSET_Y, PANEL_X, WIDTH, HEIGHT, MARGIN, my_len_min
    global Screen, x_img_org, o_img_org, x_img, o_img
    global start_img_org, pause_img_org, exit_img_org, replay_img_org, undo_img_org
    global ai_img_org, person_img_org, ai_img_gray_org, person_img_gray_org
    global h_img_org, h_img_gray_org, m_img_org, m_img_gray_org, e_img_org, e_img_gray_org
    global pvp_img_org, pvp_img_gray_org, aivp_img_org, aivp_img_gray_org
    global ai_thinking_img_org, ai_thinking_img_gray_org
    global start_img, pause_img, exit_img, replay_img, undo_img, ai_img, person_img, ai_img_gray, person_img_gray
    global h_img, h_img_gray, m_img, m_img_gray, e_img, e_img_gray
    global pvp_img, pvp_img_gray, aivp_img, aivp_img_gray, ai_thinking_img, ai_thinking_img_gray
    global icon_img, logo_img_org, logo_img
    global start_button, pause_button, replay_button, exit_button, undo_button
    global ai_btn, person_btn, h_btn, m_btn, e_btn, ai_thinking_btn, pvp_btn, aivp_btn, logo_btn
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
    ai_thinking_btn = button.Button(
        1020, 30, ai_thinking_img, ai_thinking_img_gray, 0.8)
    pvp_btn = button.Button(1075, 145, pvp_img, pvp_img_gray, 0.8)
    aivp_btn = button.Button(970, 145, aivp_img, aivp_img_gray, 0.8)
    logo_btn = button.Button(990, 660, logo_img, logo_img, 0.6)

    person_btn.disable_button()
    pvp_btn.disable_button()
    ai_thinking_btn.disable_button()
    if game_mode is not GameMode.NORMAL:
        aivp_btn.disable_button()
        pvp_btn.disable_button()
        ai_btn.disable_button()
        person_btn.disable_button()
        h_btn.disable_button()
        m_btn.disable_button()
        e_btn.disable_button()
        ai_thinking_btn.disable_button()
    else:
        h_btn.enable_button()
        m_btn.enable_button()
        e_btn.enable_button()
        if normal_mode_difficulty == 'hard':
            h_btn.disable_button()
        elif normal_mode_difficulty == 'medium':
            m_btn.disable_button()
        else:
            e_btn.disable_button()

    pygame.display.set_caption('Caro game by nhóm 12 Trí tuệ nhân tạo')
    pygame.display.set_icon(icon_img)

    my_game = caro.Caro(ROWNUM, COLNUM, winning_condition, XO)
    my_game.change_hard_ai(normal_mode_difficulty)
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
    text = font.render('By AI - nhóm 12', True, WHITE, BLACK)
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
    turn_text = small_font.render(f"Turn {my_game.XO}: {elapsed:.1f}s", True, WHITE, BLACK)
    Screen.blit(turn_text, (PANEL_X + 170, 68))


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
        text = font.render('X wins', True, RED, GREEN)
        textRect = text.get_rect()
        textRect.center = (int(Window_size[0]/2), int(Window_size[1]/2))
        Screen.blit(text, textRect)
        # done = True
    if status == 1:
        font = pygame.font.Font('freesansbold.ttf', 100)
        text = font.render('O wins', True, BLUE, GREEN)
        textRect = text.get_rect()
        textRect.center = (int(Window_size[0]/2), int(Window_size[1]/2))
        Screen.blit(text, textRect)
        # done = True


# --------- Main Program Loop -------------------------------------------
def main(argv: list[str] | None = None):
    global done, ai_is_thinking, ai_future, dev_future, ai_executor
    global normal_mode_difficulty, agent, turn_elapsed_paused, turn_started_at, turn_elapsed_frozen
    global game_mode, dev_mode_setup

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

        if (game_mode is GameMode.NORMAL and my_game.is_use_ai and my_game.turn == my_game.ai_turn
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
            if game_mode is GameMode.NORMAL:
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

        for event in pygame.event.get():  # User did something
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
            if game_mode is GameMode.NORMAL:
        # ------------- Setup button---------------------------------------------
                if len(my_game.last_move) > 0:
                    pass
                if not my_game.is_use_ai:
                    pass
                else:
                    pass

        # -----------pvp button----------------------------------------------------
                if pvp_btn.draw(Screen):
                    my_game.use_ai(False)
                    pvp_btn.disable_button()
                    aivp_btn.enable_button()
                    print("P_P")
                    pass
        # ------------ai vs p button------------------------------------------------
                if aivp_btn.draw(Screen):
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
                if h_btn.draw(Screen):
                    h_btn.disable_button()
                    m_btn.enable_button()
                    e_btn.enable_button()
                    normal_mode_difficulty = 'hard'
                    my_game.change_hard_ai("hard")
                    agent = build_player_vs_ai_agent()
                    print("Hard")
                    pass
        # ----------medium button---------------------------------------------------
                if m_btn.draw(Screen):
                    h_btn.enable_button()
                    m_btn.disable_button()
                    e_btn.enable_button()
                    normal_mode_difficulty = 'medium'
                    my_game.change_hard_ai("medium")
                    agent = build_player_vs_ai_agent()
                    print("Medium")
                    pass
        # -------------easy button--------------------------------------------------
                if e_btn.draw(Screen):
                    h_btn.enable_button()
                    m_btn.enable_button()
                    e_btn.disable_button()
                    normal_mode_difficulty = 'easy'
                    my_game.change_hard_ai("easy")
                    agent = build_player_vs_ai_agent()
                    print("Easy")
                    pass
        # -------Choose person play first button------------------------------------
                if person_btn.draw(Screen):  # Ấn nút Chọn người đi trước
                    person_btn.disable_button()
                    ai_btn.enable_button()
                    my_game.set_ai_turn(2)
                    agent = build_player_vs_ai_agent()
                    print("Human")
                    pass
        # -------Choose AI play first button------------------------------------
                if ai_btn.draw(Screen):  # Ấn nút Chọn AI đi trước
                    ai_btn.disable_button()
                    person_btn.enable_button()
                    my_game.set_ai_turn(1)
                    agent = build_player_vs_ai_agent()
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
            if game_mode is not GameMode.NORMAL and SHOW_DEV_START_DEBUG_BORDER:
                pygame.draw.rect(Screen, (255, 255, 0), start_button.rect, 3)
                pygame.draw.rect(Screen, (0, 255, 255), pause_button.rect, 3)
            checking_winning(status)
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