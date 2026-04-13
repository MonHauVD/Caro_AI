# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

# Gói extension Cython (build truoc: python setup_cython.py build_ext --inplace).
# Khong co .pyd/.so thi EXE van build duoc nhung agent.py se fallback Python (cham hon).
try:
    _spec_root = Path(SPECPATH)
except NameError:
    _spec_root = Path(__file__).resolve().parent

_cy_binaries = []
for _pattern in (
    'agent_accel*.pyd',
    'search_accel*.pyd',
    'agent_accel*.so',
    'search_accel*.so',
):
    for _p in _spec_root.glob(_pattern):
        if _p.is_file():
            _cy_binaries.append((str(_p), '.'))

_hidden = [
    'caro_ai',
    'caro_ai.app',
    'caro_ai.game',
    'caro_ai.game.caro',
    'caro_ai.ui',
    'caro_ai.ui.buttons',
    'caro_ai.ui.layout',
    'caro_ai.ai',
    'caro_ai.ai.agent',
    'caro_ai.modes',
    # Benchmark (report_merge / merge_cli: import lười hoặc nhánh __main__ — cần khai báo rõ).
    'caro_ai.benchmark',
    'caro_ai.benchmark.session',
    'caro_ai.benchmark.multi',
    'caro_ai.benchmark.worker',
    'caro_ai.benchmark.report_merge',
    'caro_ai.benchmark.merge_cli',
]
if any(_spec_root.glob('agent_accel*.pyd')) or any(_spec_root.glob('agent_accel*.so')):
    _hidden.append('agent_accel')
if any(_spec_root.glob('search_accel*.pyd')) or any(_spec_root.glob('search_accel*.so')):
    _hidden.append('search_accel')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_cy_binaries,
    datas=[('assets', 'assets'), ('config', 'config')],
    hiddenimports=_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
