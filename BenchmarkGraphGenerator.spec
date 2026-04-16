# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=[],
    datas=collect_data_files("matplotlib"),
    hiddenimports=[
        "matplotlib.backends.backend_tkagg",
        "matplotlib.backends._backend_tk",
        "matplotlib.backends.backend_svg",
        "matplotlib.backends.backend_agg",
        "matplotlib.backends.backend_pdf",
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.simpledialog",
        "tkinter.colorchooser",
        "tkinter.scrolledtext",
        "pandas._libs.tslibs.np_datetime",
        "pandas._libs.tslibs.nattype",
        "pandas._libs.tslibs.timedeltas",
        "unittest",
        "unittest.mock",
        "unittest.case",
        "unittest.util",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BenchmarkGraphGenerator",
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # no terminal window
    icon=None,       # replace with "icon.ico" if you add one
)
