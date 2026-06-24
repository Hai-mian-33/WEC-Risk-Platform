# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置 —— WEC-Risk Platform
==========================================
处理三类难点：
  1) PyQt5 QtWebEngine 运行时（QtWebEngineProcess.exe + resources + locales）
  2) geopandas/pyproj/shapely/pyogrio 的数据文件（尤其 pyproj 的 proj.db）
  3) folium/branca 的模板与静态资源

构建： pyinstaller wec_platform.spec --noconfirm
产物： dist/WEC_Platform/WEC_Platform.exe （onedir，启动快、便于排错）
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

datas = []
binaries = []
hiddenimports = []

# folium / branca：模板与静态文件（小，collect_all 安全）
for pkg in ("folium", "branca"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

# pyogrio：geopandas 默认矢量 IO 后端（含 GDAL DLL/数据）
d, b, h = collect_all("pyogrio")
datas += d; binaries += b; hiddenimports += h

# 地理栈数据文件（pyproj 的 proj.db 必须随包）
datas += collect_data_files("pyproj")
datas += collect_data_files("geopandas")
datas += collect_data_files("shapely")

# 仅声明必要隐藏导入；scipy/sklearn/PyQt5 由 PyInstaller 内置 hook 处理，
# 不用 collect_submodules（会在 spec 执行阶段递归 import 整个包导致卡死）。
hiddenimports += ["dbfread", "pyproj", "shapely", "geopandas", "pandas", "numpy",
                  "sklearn.utils._typedefs", "sklearn.neighbors._partition_nodes",
                  "matplotlib.backends.backend_qt5agg"]

# 内置示例工程
datas += [("examples/miyun_project.json", "examples")]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # 用 pyogrio 后端排除 fiona；排除环境中存在但本程序不用的重型库，
    # 否则 PyInstaller 会把 TensorFlow/torch 等一并打入，致 exe 巨大且构建极慢。
    excludes=[
        "tkinter", "fiona",
        "tensorflow", "tensorboard", "keras", "tensorflow_intel",
        "torch", "torchvision", "torchaudio",
        "jax", "jaxlib", "flax", "transformers",
        "cv2", "numba", "llvmlite", "IPython", "notebook", "jupyter",
        "pytest", "sphinx", "PySide2", "PySide6", "PyQt6",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="WEC_Platform",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # 无控制台窗口（GUI 程序）
    disable_windowed_traceback=False,
    icon=None,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=False, upx_exclude=[],
    name="WEC_Platform",
)
