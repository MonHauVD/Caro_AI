# Caro_AI

The Caro AI game with a strong heuristic AI built on minimax and alpha-beta pruning. The codebase has grown from a compact student project into a version with deeper search, optional native acceleration, benchmark tooling, and configurable difficulty.

---

## Version note

### Original baseline (early README / classic behavior)

- Core AI: **minimax** with **alpha-beta pruning**.
- Run the game with **Python** and **Pygame** after installing dependencies from `requirements.txt`.
- Entry point: `main.py`.
- Packaged release was described as a downloadable archive; development setup used `pip install pygame` (and optional Tk on Linux for some environments).

### Current version (what is new)

Search and evaluation:

- **Move ordering** so alpha-beta cuts branches earlier.
- **Transposition table** with **Zobrist hashing** to reuse scores for repeated positions.
- **Beam search / forward pruning** (configurable beam widths).
- **Incremental evaluation** to update heuristic locally instead of rescanning the board.
- **Iterative deepening** with reuse of prior principal variation for ordering.
- **Threat-oriented search** (VCF-style tactical layer) and related options, configurable per agent.
- **Time budget per move** (`move_time_budget_sec`); search can stop between completed depths and keep the last fully finished result.
- **Adaptive depth / beam** by game stage where enabled.

Performance:

- Optional **Cython extensions**: heuristic acceleration (`agent_accel`) and a compiled minimax path (`search_accel`). Build with `setup_cython.py` (see below).
- Optional **lazy SMP** (parallel root helpers) where configured.
- **AI move computation in a worker process** so the Pygame loop stays responsive while the agent thinks.

Gameplay and UI:

- **Resizable window** with layout that scales the board and controls.
- **Single turn timer** for the active side; timer stops when the game ends.
- **Player vs AI** and **AI vs AI (developer mode)** with Start / Pause (dev and benchmark), Undo, Replay.
- **Player vs AI difficulty** is no longer “depth only”: **Easy / Medium / Hard** map to full **preset configs** (`PLAYER_VS_AI_PRESETS` at the top of `main.py`: depth plus all relevant `Agent` options).

Benchmarking and analysis:

- **Benchmark mode** runs scheduled matchups from an external **`benchmark_config.json`** (merged over any inline `benchmark_setup` defaults in `main.py`).
- Results append incrementally to:
  - `benchmark_results_summary.txt` — structured fields per game.
  - `benchmark_results_boards.txt` — ASCII board, agents, outcome per side.
- **Resume**: on a fresh program start, benchmark mode can advance to the **next** matchup/game based on the last valid `match_id` in the summary file (entries that do not match the current config are ignored).
- **`benchmark_analysis.ipynb`**: parse the text outputs and plot win rates, timings, Elo-style summaries, heatmaps, etc.

---

## How to use (current project)

### 1. Choose the mode in `main.py`

At the top of `main.py`:

- **`is_developer_mode`**: `False` for normal **human vs AI**; `True` for **AI vs AI** (developer / watch mode).
- **`benchmark_mode`**: `True` only when you want the automated benchmark runner; otherwise set `False` for interactive play.

Typical **human vs AI** setup:

- `is_developer_mode = False`
- `benchmark_mode = False`

Then run `main.py` and use the on-screen buttons (AI vs Player, difficulty, who moves first, etc.).

### 2. Player vs AI difficulty presets

Edit **`PLAYER_VS_AI_PRESETS`** near the top of `main.py`. Each of `easy`, `medium`, and `hard` has:

- **`depth`**: search depth for that preset.
- **`config`**: full agent configuration (Cython search, TSS, lazy SMP, beam widths, time budget, and any other keys supported by `Agent`).

The in-game **E / M / H** buttons select which preset is active and rebuild the agent.

### 3. Developer mode (AI vs AI)

With `is_developer_mode = True` and `benchmark_mode = False`:

- Configure **`dev_mode_setup`**: depths, `ai_1_config` / `ai_2_config`, and piece sides.
- Use **Start** to begin (timer behavior follows the existing dev-mode rules).
- **Pause** stops the match loop and, when combined with benchmark-style hard-stop, cancels in-flight worker computation; **Start** resumes from the current board state.

### 4. Benchmark mode

With **`benchmark_mode = True`**:

- Edit **`benchmark_config.json`** in the project root: `games_per_matchup`, `matchups` (each with `name`, `agent_a`, `agent_b`, labels, depths, and per-agent `config`).
- Press **Start** in the UI to begin (exact wiring is in `main.py`).
- **Pause** pauses the benchmark run and stops the worker; **Start** resumes.
- **Replay** (in benchmark) restarts the **current** scheduled game for the current pair without advancing the schedule.
- Output files **`benchmark_results_summary.txt`** and **`benchmark_results_boards.txt`** grow by append; restarting the app can **resume** from the last completed valid game if the config still matches.

### 5. Analysis notebook

Open **`benchmark_analysis.ipynb`** in Jupyter, ensure the summary and boards text files are present, and run the cells to regenerate tables and plots.

---

## Optional: Cython build (faster search / eval)

Install build tools:

```bash
pip install cython setuptools
```

Compile extensions in the project directory:

```bash
python3 setup_cython.py build_ext --inplace
```

On Windows, use `python setup_cython.py build_ext --inplace` if `python3` is not on your PATH.

If extensions are missing, the game can still run with the pure-Python paths where configured.

---

## Requirements and run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python3 main.py
```

(or `python main.py` on Windows)

---

## Screenshot

![playground](image/playground.png)

![xwins](image/xwins.png)

---

## Development environment

Python version: **3.11**

### Linux

Optional Tk (if your tooling needs it):

```bash
sudo apt install python3.11-tk
```

Then install Pygame and requirements as above.

### Windows

Install Pygame and requirements with `pip` as usual.

---

## Tags

#Caro #CaroAI #Github #Minimax #AlphaBeta
