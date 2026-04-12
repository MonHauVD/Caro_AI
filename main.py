import Buttons as button
import pygame
import sys
import caro
import os
import time
import copy
import json
from concurrent.futures import ProcessPoolExecutor
from agent import Agent

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
        'depth': 7,
        'config': {
            'use_cython_search': False,
            'use_tss': False,
            'use_lazy_smp': False,
            'beam_width_root': 12,
            'beam_width_inner': 9,
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

# Đồng bộ với UI: mặc định Medium (nút M đang disable lúc khởi động).
normal_mode_difficulty = 'medium'

# developer_mode: ai vs ai
# Đặt is_developer_mode = True nếu muốn cho ai đấu với ai

is_developer_mode = False
# is_developer_mode = True
benchmark_mode = False

dev_mode_setup = {
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
benchmark_setup = {
    'games_per_matchup': 4,  # Auto-swap first move by alternating X/O each game.
    'output_dir': 'benchmark_results',
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

BENCHMARK_CONFIG_FILE = "benchmark_config.json"
BENCHMARK_RESULT_SUMMARY_FILE = "benchmark_results_summary.txt"
BENCHMARK_RESULT_BOARD_FILE = "benchmark_results_boards.txt"
# init game and ai
my_game = caro.Caro(ROWNUM, COLNUM, winning_condition, XO)
my_game.change_hard_ai(normal_mode_difficulty)


def build_player_vs_ai_agent() -> Agent:
    preset = PLAYER_VS_AI_PRESETS[normal_mode_difficulty]
    cfg = copy.deepcopy(preset['config'])
    return Agent(
        max_depth=preset['depth'],
        XO=my_game.get_current_XO_for_AI(),
        config=cfg,
        log_init=False,
    )


agent = build_player_vs_ai_agent()

agent1 = Agent(max_depth=dev_mode_setup['ai_1_depth'],
                       XO=dev_mode_setup['ai_1'],
                       config=dev_mode_setup['ai_1_config'])
agent2 = Agent(max_depth=dev_mode_setup['ai_2_depth'],
                       XO=dev_mode_setup['ai_2'],
                       config=dev_mode_setup['ai_2_config'])

Window_size = [1280, 720]
BOARD_OFFSET_X = 0
BOARD_OFFSET_Y = 0
PANEL_X = 920
START_BTN_ANCHOR_TOP = 120
START_BTN_ANCHOR_RIGHT_MARGIN = 60
SHOW_DEV_START_DEBUG_BORDER = True

my_len_min = min(900 / COLNUM, (720) / ROWNUM)
MARGIN = my_len_min / 15
my_len_min = min((900 - MARGIN) / COLNUM, (720 - MARGIN) / ROWNUM)
my_len_min = my_len_min - MARGIN
WIDTH = my_len_min
HEIGHT = my_len_min

Screen = pygame.display.set_mode(Window_size, pygame.RESIZABLE)
# path = "Caro/asset"
path = os.getcwd()
path = os.path.join(path, './asset')

# ------------------------------Load asset----------------------------------------
x_img_org = pygame.image.load(path + "/X_caro.png").convert_alpha()
o_img_org = pygame.image.load(path + "/O_caro.png").convert_alpha()
x_img = pygame.transform.smoothscale(x_img_org, (int(my_len_min), int(my_len_min)))
o_img = pygame.transform.smoothscale(o_img_org, (int(my_len_min), int(my_len_min)))
# load button images
start_img_org = pygame.image.load(path + '/start_btn.png').convert_alpha()
pause_img_org = pygame.image.load(path + '/pause_btn.png').convert_alpha()
exit_img_org = pygame.image.load(path + '/exit_btn.png').convert_alpha()
replay_img_org = pygame.image.load(path + '/replay_btn.png').convert_alpha()
undo_img_org = pygame.image.load(path + '/undo_btn.png').convert_alpha()
ai_img_org = pygame.image.load(path + '/ai_btn.png').convert_alpha()
person_img_org = pygame.image.load(path + '/person_btn.png').convert_alpha()
ai_img_gray_org = pygame.image.load(path + '/ai_btn_gray.jpg').convert_alpha()
person_img_gray_org = pygame.image.load(path + '/person_btn_gray.jpg').convert_alpha()
h_img_org = pygame.image.load(path + '/h_btn.png').convert_alpha()
h_img_gray_org = pygame.image.load(path + '/h_btn_gray.png').convert_alpha()
m_img_org = pygame.image.load(path + '/m_btn.png').convert_alpha()
m_img_gray_org = pygame.image.load(path + '/m_btn_gray.png').convert_alpha()
e_img_org = pygame.image.load(path + '/e_btn.png').convert_alpha()
e_img_gray_org = pygame.image.load(path + '/e_btn_gray.png').convert_alpha()
pvp_img_org = pygame.image.load(path + '/player_vs_player.jpg').convert_alpha()
pvp_img_gray_org = pygame.image.load(path + '/player_vs_player_gray.jpg').convert_alpha()
aivp_img_org = pygame.image.load(path + '/ai_vs_player.jpg').convert_alpha()
aivp_img_gray_org = pygame.image.load(path + '/ai_vs_player_gray.jpg').convert_alpha()
ai_thinking_img_org = pygame.image.load(path + '/ai_thinking.png').convert_alpha()
ai_thinking_img_gray_org = pygame.image.load(path + '/ai_thinking_gray.png').convert_alpha()

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
icon_img = pygame.transform.smoothscale(pygame.image.load(
    path + '/old/icon.jpg').convert_alpha(), (20, 20))
logo_img_org = pygame.image.load(path + '/logo.jpg').convert_alpha()
logo_img = pygame.transform.smoothscale(logo_img_org, (240, 105))
# create button instances
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
m_btn.disable_button()
pvp_btn.disable_button()
ai_thinking_btn.disable_button()
if (is_developer_mode == True):
    aivp_btn.disable_button()
    pvp_btn.disable_button()
    ai_btn.disable_button()
    person_btn.disable_button()
    h_btn.disable_button()
    m_btn.disable_button()
    e_btn.disable_button()
    ai_thinking_btn.disable_button()

pygame.display.set_caption('Caro game by nhóm 12 Trí tuệ nhân tạo')
pygame.display.set_icon(icon_img)
pygame.init()


# Loop until the user clicks the close button.
done = False
status = my_game.get_winner()
# Used to manage how fast the screen updates
clock = pygame.time.Clock()
turn_started_at = time.perf_counter()
turn_elapsed_frozen = None
turn_timer_paused = False
turn_elapsed_paused = 0.0
ai_is_thinking = False
ai_future = None
dev_future = None
ai_executor = ProcessPoolExecutor(max_workers=1)
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
}

# ----------------------- Function ------------------------------------
def set_button_position(btn: button.Button, x: int, y: int):
    btn.x = x
    btn.y = y
    btn.rect.topleft = (x, y)


def set_button_scale(btn: button.Button, normal_img, gray_img, scale: float):
    btn.image = pygame.transform.smoothscale(
        normal_img,
        (max(20, int(normal_img.get_width() * scale)), max(20, int(normal_img.get_height() * scale))),
    )
    btn.gray_image = pygame.transform.smoothscale(
        gray_img,
        (max(20, int(gray_img.get_width() * scale)), max(20, int(gray_img.get_height() * scale))),
    )
    btn.rect = btn.image.get_rect(topleft=(btn.x, btn.y))


def update_layout(new_width: int, new_height: int):
    global Window_size, WIDTH, HEIGHT, MARGIN
    global BOARD_OFFSET_X, BOARD_OFFSET_Y, PANEL_X, x_img, o_img

    new_width = max(980, int(new_width))
    new_height = max(640, int(new_height))
    Window_size[0] = new_width
    Window_size[1] = new_height

    panel_width = max(320, int(new_width * 0.28))
    board_available_w = max(200, new_width - panel_width - 30)
    board_available_h = max(200, new_height - 20)
    cell_total = max(8, int(min(board_available_w / COLNUM, board_available_h / ROWNUM)))
    MARGIN = max(1, cell_total // 15)
    WIDTH = max(6, cell_total - MARGIN)
    HEIGHT = WIDTH

    board_pixel_w = COLNUM * (WIDTH + MARGIN) + MARGIN
    board_pixel_h = ROWNUM * (HEIGHT + MARGIN) + MARGIN
    BOARD_OFFSET_X = max(5, int((board_available_w - board_pixel_w) / 2))
    BOARD_OFFSET_Y = max(5, int((new_height - board_pixel_h) / 2))
    PANEL_X = int(BOARD_OFFSET_X + board_pixel_w + 20)

    x_img = pygame.transform.smoothscale(x_img_org, (max(6, int(WIDTH)), max(6, int(HEIGHT))))
    o_img = pygame.transform.smoothscale(o_img_org, (max(6, int(WIDTH)), max(6, int(HEIGHT))))

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

    set_button_position(replay_button, PANEL_X + 30, new_height - 145)
    set_button_position(exit_button, PANEL_X + 30, new_height - 235)
    set_button_position(undo_button, PANEL_X + 30, new_height - 325)
    # Keep dev start/pause stacked above Undo button.
    pause_x = undo_button.rect.x
    pause_y = max(40, undo_button.rect.y - pause_button.rect.height - 12)
    start_x = undo_button.rect.x
    start_y = max(40, pause_y - start_button.rect.height - 12)
    set_button_position(start_button, start_x, start_y)
    set_button_position(pause_button, pause_x, pause_y)
    set_button_position(ai_btn, PANEL_X + 30, 305)
    set_button_position(person_btn, PANEL_X + 135, 305)
    set_button_position(h_btn, PANEL_X + 160, 235)
    set_button_position(m_btn, PANEL_X + 95, 235)
    set_button_position(e_btn, PANEL_X + 30, 235)
    set_button_position(ai_thinking_btn, PANEL_X + 80, 30)
    set_button_position(pvp_btn, PANEL_X + 135, 145)
    set_button_position(aivp_btn, PANEL_X + 30, 145)
    set_button_position(logo_btn, PANEL_X + 50, new_height - 55)


update_layout(Window_size[0], Window_size[1])


def logo():
    font = pygame.font.Font('freesansbold.ttf', 36)
    text = font.render('By AI - nhóm 12', True, WHITE, BLACK)
    textRect = text.get_rect()
    textRect.center = (PANEL_X + 150, Window_size[1] - 20)
    Screen.blit(text, textRect)
    # logo_btn.draw(Screen)
    if is_developer_mode:
        font = pygame.font.Font('freesansbold.ttf', 36)
        text = font.render('Developer_Mode', True, WHITE, BLACK)
        textRect = text.get_rect()
        textRect.center = (PANEL_X + 140, 160)
        Screen.blit(text, textRect)
    small_font = pygame.font.Font('freesansbold.ttf', 24)
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


def compute_ai_move_worker(game_snapshot: caro.Caro, max_depth: int, xo: str, agent_config: dict | None = None) -> list[int]:
    worker_agent = Agent(max_depth=max_depth, XO=xo, config=agent_config, log_init=False)
    return worker_agent.get_move(game_snapshot)


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


def load_benchmark_config():
    config_path = os.path.join(os.getcwd(), BENCHMARK_CONFIG_FILE)
    if not os.path.exists(config_path):
        return
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            benchmark_setup.update(loaded)
            print(f"[BENCH] loaded config from {config_path}")
    except Exception as ex:
        print(f"[BENCH] failed to load config file {config_path}: {ex}")


def _parse_match_id(match_id: str) -> tuple[str, int] | None:
    if "__game_" not in match_id:
        return None
    matchup_name, game_part = match_id.rsplit("__game_", 1)
    try:
        game_no = int(game_part)
    except Exception:
        return None
    return matchup_name, game_no


def detect_benchmark_resume_position() -> tuple[int, int]:
    matchups = benchmark_setup.get('matchups', [])
    games_per_matchup = max(1, int(benchmark_setup.get('games_per_matchup', 1)))
    if not matchups:
        return 0, 0

    summary_path = os.path.join(os.getcwd(), BENCHMARK_RESULT_SUMMARY_FILE)
    if not os.path.exists(summary_path):
        return 0, 0

    matchup_name_to_idx = {}
    for idx, matchup in enumerate(matchups):
        name = matchup.get('name')
        if isinstance(name, str) and name != "":
            matchup_name_to_idx[name] = idx

    last_valid: tuple[int, int] | None = None
    ignored_count = 0
    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line.startswith("match_id="):
                    continue
                match_id = line.split("=", 1)[1].strip()
                parsed = _parse_match_id(match_id)
                if parsed is None:
                    ignored_count += 1
                    continue
                matchup_name, game_no = parsed
                matchup_idx = matchup_name_to_idx.get(matchup_name)
                if matchup_idx is None:
                    ignored_count += 1
                    continue
                if game_no < 1 or game_no > games_per_matchup:
                    ignored_count += 1
                    continue
                last_valid = (matchup_idx, game_no)
    except Exception as ex:
        print(f"[BENCH] failed to inspect summary for resume: {ex}")
        return 0, 0

    if ignored_count > 0:
        print(f"[BENCH] ignored {ignored_count} summary entries not in current config or invalid")

    if last_valid is None:
        print("[BENCH] no valid previous result found; start from first game")
        return 0, 0

    next_matchup_idx, last_game_no = last_valid
    next_game_idx = last_game_no  # next zero-based game index after completed game_no
    if next_game_idx >= games_per_matchup:
        next_matchup_idx += 1
        next_game_idx = 0

    if next_matchup_idx >= len(matchups):
        print("[BENCH] previous run already reached end of configured matchups; start from first game")
        return 0, 0

    print(
        f"[BENCH] resume next game at matchup_idx={next_matchup_idx}, game_idx={next_game_idx}"
    )
    return next_matchup_idx, next_game_idx


def board_to_ascii(this_game: caro.Caro) -> str:
    return "\n".join(" ".join(row) for row in this_game.grid)


def write_benchmark_reports():
    summary_path = os.path.join(os.getcwd(), BENCHMARK_RESULT_SUMMARY_FILE)
    board_path = os.path.join(os.getcwd(), BENCHMARK_RESULT_BOARD_FILE)

    lines_summary = []
    lines_board = []

    for result in benchmark_state['results']:
        lines_summary.append(f"match_id={result['match_id']}")
        lines_summary.append(f"agent_x={json.dumps(result['agent_x'], ensure_ascii=False)}")
        lines_summary.append(f"agent_o={json.dumps(result['agent_o'], ensure_ascii=False)}")
        lines_summary.append(f"winner={result['winner_label']}")
        lines_summary.append(
            "stats="
            + json.dumps(
                {
                    "x_avg_move_sec": result['x_avg_move_sec'],
                    "o_avg_move_sec": result['o_avg_move_sec'],
                    "x_moves": result['x_moves'],
                    "o_moves": result['o_moves'],
                    "winner_code": result['winner_code'],
                },
                ensure_ascii=False,
            )
        )
        lines_summary.append(f"board_ref={result['match_id']}")
        lines_summary.append("")

        lines_board.append(f"match_id={result['match_id']}")
        lines_board.append(result['board_ascii'])
        lines_board.append("")

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_summary).strip() + "\n")
    with open(board_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_board).strip() + "\n")

    print(f"[BENCH] wrote summary to {summary_path}")
    print(f"[BENCH] wrote board-ascii to {board_path}")


def reset_benchmark_report_files():
    summary_path = os.path.join(os.getcwd(), BENCHMARK_RESULT_SUMMARY_FILE)
    board_path = os.path.join(os.getcwd(), BENCHMARK_RESULT_BOARD_FILE)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("")
    with open(board_path, "w", encoding="utf-8") as f:
        f.write("")
    print(f"[BENCH] reset report files: {summary_path}, {board_path}")


def append_benchmark_result_to_files(result: dict):
    summary_path = os.path.join(os.getcwd(), BENCHMARK_RESULT_SUMMARY_FILE)
    board_path = os.path.join(os.getcwd(), BENCHMARK_RESULT_BOARD_FILE)

    with open(summary_path, "a", encoding="utf-8") as f:
        f.write(f"match_id={result['match_id']}\n")
        f.write(f"agent_x={json.dumps(result['agent_x'], ensure_ascii=False)}\n")
        f.write(f"agent_o={json.dumps(result['agent_o'], ensure_ascii=False)}\n")
        f.write(f"winner={result['winner_label']}\n")
        f.write(
            "stats="
            + json.dumps(
                {
                    "x_avg_move_sec": result['x_avg_move_sec'],
                    "o_avg_move_sec": result['o_avg_move_sec'],
                    "x_moves": result['x_moves'],
                    "o_moves": result['o_moves'],
                    "winner_code": result['winner_code'],
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        f.write(f"board_ref={result['match_id']}\n\n")

    with open(board_path, "a", encoding="utf-8") as f:
        f.write(f"match_id={result['match_id']}\n")
        f.write(f"winner={result['winner_label']}\n")
        f.write(f"agent_x={json.dumps(result['agent_x'], ensure_ascii=False)}\n")
        f.write(f"agent_o={json.dumps(result['agent_o'], ensure_ascii=False)}\n")
        if result['winner_label'] == 'draw':
            f.write("result_for_agent_x=draw\n")
            f.write("result_for_agent_o=draw\n")
        else:
            x_label = result['agent_x']['label']
            o_label = result['agent_o']['label']
            f.write(f"result_for_agent_x={'win' if result['winner_label'] == x_label else 'loss'}\n")
            f.write(f"result_for_agent_o={'win' if result['winner_label'] == o_label else 'loss'}\n")
        f.write(result['board_ascii'] + "\n\n")


def _new_agent_stats():
    return {'wins': 0, 'losses': 0, 'draws': 0, 'move_time_total': 0.0, 'move_count': 0}


def benchmark_record_move(agent_key: str, elapsed: float | None):
    if elapsed is None:
        return
    current = benchmark_state['current']
    if current is None:
        return
    current['stats'][agent_key]['move_time_total'] += elapsed
    current['stats'][agent_key]['move_count'] += 1


def benchmark_setup_game():
    global agent1, agent2, turn_started_at, turn_elapsed_frozen, dev_future, ai_is_thinking
    matchup = benchmark_setup['matchups'][benchmark_state['matchup_idx']]
    game_idx = benchmark_state['game_idx']
    match_id = f"{matchup['name']}__game_{game_idx + 1}"

    swap = (game_idx % 2 == 1)
    a = matchup['agent_a']
    b = matchup['agent_b']
    x_side = b if swap else a
    o_side = a if swap else b

    my_game.reset()
    my_game.use_ai(True)
    my_game.set_ai_turn(2)  # ignored in dev-mode benchmark flow
    update_game_status(my_game.get_winner())
    turn_started_at = time.perf_counter()
    turn_elapsed_frozen = None
    set_turn_timer_pause(False)

    agent1 = Agent(max_depth=x_side['depth'], XO='X', config=x_side['config'])
    agent2 = Agent(max_depth=o_side['depth'], XO='O', config=o_side['config'])

    benchmark_state['current'] = {
        'matchup_name': matchup['name'],
        'game_idx': game_idx,
        'swap': swap,
        'x_label': x_side['label'],
        'o_label': o_side['label'],
        'x_config': {'depth': x_side['depth'], **x_side['config']},
        'o_config': {'depth': o_side['depth'], **o_side['config']},
        'stats': {
            x_side['label']: _new_agent_stats(),
            o_side['label']: _new_agent_stats(),
        },
    }
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
    current = benchmark_state['current']
    if current is None:
        return
    winner = my_game.get_winner()
    x_label = current['x_label']
    o_label = current['o_label']
    if winner == 0:
        current['stats'][x_label]['wins'] += 1
        current['stats'][o_label]['losses'] += 1
    elif winner == 1:
        current['stats'][o_label]['wins'] += 1
        current['stats'][x_label]['losses'] += 1
    else:
        current['stats'][x_label]['draws'] += 1
        current['stats'][o_label]['draws'] += 1

    matchup_name = current['matchup_name']
    if matchup_name not in benchmark_state['stats']:
        benchmark_state['stats'][matchup_name] = {}
    for label, s in current['stats'].items():
        if label not in benchmark_state['stats'][matchup_name]:
            benchmark_state['stats'][matchup_name][label] = _new_agent_stats()
        agg = benchmark_state['stats'][matchup_name][label]
        agg['wins'] += s['wins']
        agg['losses'] += s['losses']
        agg['draws'] += s['draws']
        agg['move_time_total'] += s['move_time_total']
        agg['move_count'] += s['move_count']

    x_stat = current['stats'][x_label]
    o_stat = current['stats'][o_label]
    x_avg = (x_stat['move_time_total'] / x_stat['move_count']) if x_stat['move_count'] else 0.0
    o_avg = (o_stat['move_time_total'] / o_stat['move_count']) if o_stat['move_count'] else 0.0

    if winner == 0:
        winner_label = x_label
    elif winner == 1:
        winner_label = o_label
    else:
        winner_label = "draw"

    match_id = f"{matchup_name}__game_{current['game_idx'] + 1}"
    result_entry = {
        'match_id': match_id,
        'agent_x': {'label': x_label, 'config': current['x_config']},
        'agent_o': {'label': o_label, 'config': current['o_config']},
        'winner_label': winner_label,
        'winner_code': winner,
        'x_avg_move_sec': round(x_avg, 4),
        'o_avg_move_sec': round(o_avg, 4),
        'x_moves': x_stat['move_count'],
        'o_moves': o_stat['move_count'],
        'board_ascii': board_to_ascii(my_game),
    }
    benchmark_state['results'].append(result_entry)
    append_benchmark_result_to_files(result_entry)


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
load_benchmark_config()
while not done:
    if benchmark_mode and not benchmark_state['initialized']:
        benchmark_state['initialized'] = True
        benchmark_state['running'] = False
        resume_matchup_idx, resume_game_idx = detect_benchmark_resume_position()
        benchmark_state['resume_matchup_idx'] = resume_matchup_idx
        benchmark_state['resume_game_idx'] = resume_game_idx
        benchmark_state['matchup_idx'] = resume_matchup_idx
        benchmark_state['game_idx'] = resume_game_idx
        benchmark_state['stats'] = {}
        benchmark_state['results'] = []
        my_game.reset()
        update_game_status(my_game.get_winner())
        set_turn_timer_pause(True)
        print("[BENCH] waiting for Start button")

    if benchmark_mode:
        if benchmark_state['running'] and benchmark_state['matchup_idx'] < len(benchmark_setup['matchups']):
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
                            elapsed = apply_move_with_timer(my_game, best_move[0], best_move[1], actor=current_actor)
                            benchmark_record_move(current_actor, elapsed)
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
                        for matchup_name, matchup_stats in benchmark_state['stats'].items():
                            print(f"[BENCH][{matchup_name}]")
                            for label, s in matchup_stats.items():
                                avg = (s['move_time_total'] / s['move_count']) if s['move_count'] else 0.0
                                print(f"  {label}: W={s['wins']} L={s['losses']} D={s['draws']} avg_move={avg:.3f}s")

    if (not benchmark_mode and not is_developer_mode and my_game.is_use_ai and my_game.turn == my_game.ai_turn
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
        if (not is_developer_mode) and (not benchmark_mode):
            ai_is_thinking = False
            ai_thinking_btn.disable_button()

    if (not benchmark_mode) and is_developer_mode and status == -1 and dev_mode_setup['start'] and not dev_mode_setup['pause']:
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
    elif (not benchmark_mode) and is_developer_mode:
        if dev_future is not None and dev_future.done():
            dev_future = None
        if not dev_mode_setup['start']:
            ai_is_thinking = False
            ai_thinking_btn.disable_button()

    for event in pygame.event.get():  # User did something

# ---------------- Undo button ---------------------------------------------
        if undo_button.draw(Screen):  # Ấn nút Undo
            if benchmark_mode:
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
            if is_developer_mode:
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
        if exit_button.draw(Screen):  # Ấn nút Thoát
            print('EXIT')
            # quit game
            done = True
# --------------Replay button-------------------------------------------
        if replay_button.draw(Screen):  # Ấn nút Chơi lại
            if benchmark_mode:
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
            if is_developer_mode:
                dev_mode_setup['pause'] = False
                set_turn_timer_pause(False)
            turn_started_at = time.perf_counter()
            turn_elapsed_frozen = None
            update_game_status(my_game.get_winner())
            re_draw()
# ---------Normal mode---------------------------------------------------
        if not is_developer_mode:
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
                if benchmark_mode:
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
            if benchmark_mode:
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
                        benchmark_state['running'] = True
                        turn_elapsed_paused = 0.0
                        turn_started_at = time.perf_counter()
                        set_turn_timer_pause(False)
                        print("[BENCH] resumed current game")
                    else:
                        if ai_executor is None:
                            ai_executor = ProcessPoolExecutor(max_workers=1)
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
            else:
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
            ai_thinking_btn.re_draw(Screen)

# ------ Draw screen---------------------------------------------------
    draw(my_game, Screen)
    if is_developer_mode and SHOW_DEV_START_DEBUG_BORDER:
        pygame.draw.rect(Screen, (255, 255, 0), start_button.rect, 3)
        pygame.draw.rect(Screen, (0, 255, 255), pause_button.rect, 3)
# -------- checking winner --------------------------------------------
    checking_winning(status)
# Limit to 999999999 frames per second
    clock.tick(FPS)

    # Go ahead and update the screen with what we've drawn.
    pygame.display.update()

pygame.time.delay(50)
if ai_executor is not None:
    ai_executor.shutdown(wait=False, cancel_futures=True)
quit()
pygame.quit()
sys.exit()
