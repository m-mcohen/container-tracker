# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('app.ico', '.')]
binaries = []
hiddenimports = []

# PySide6: platforms, imageformats, styles — required or the app crashes at launch
# on machines without Qt installed system-wide. We rely on PyInstaller's bundled
# PySide6 hook for module collection and use `excludes` to drop the heavy optional
# Qt modules the app does not import (Qt3D, QtWebEngine, QtCharts, multimedia, etc.).
# `collect_all('PySide6')` pulls everything and produces a 250 MB+ exe that hangs
# during onefile extraction.

# keyring: Windows Credential Manager backend is discovered dynamically; PyInstaller
# otherwise misses keyring.backends.Windows.
tmp_ret = collect_all('keyring')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['container_tracker/__main__.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy PySide6 optional modules the app does not import.
        'PySide6.Qt3DAnimation', 'PySide6.Qt3DCore', 'PySide6.Qt3DExtras',
        'PySide6.Qt3DInput', 'PySide6.Qt3DLogic', 'PySide6.Qt3DRender',
        'PySide6.QtAxContainer', 'PySide6.QtBluetooth', 'PySide6.QtCharts',
        'PySide6.QtDataVisualization', 'PySide6.QtDBus', 'PySide6.QtDesigner',
        'PySide6.QtGraphs', 'PySide6.QtGraphsWidgets', 'PySide6.QtHelp',
        'PySide6.QtHttpServer', 'PySide6.QtLocation', 'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets', 'PySide6.QtNfc', 'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets',
        'PySide6.QtPositioning', 'PySide6.QtPrintSupport', 'PySide6.QtQml',
        'PySide6.QtQuick', 'PySide6.QtQuick3D', 'PySide6.QtQuickControls2',
        'PySide6.QtQuickTest', 'PySide6.QtQuickWidgets', 'PySide6.QtRemoteObjects',
        'PySide6.QtScxml', 'PySide6.QtSensors', 'PySide6.QtSerialBus',
        'PySide6.QtSerialPort', 'PySide6.QtSpatialAudio', 'PySide6.QtSql',
        'PySide6.QtStateMachine', 'PySide6.QtSvg', 'PySide6.QtSvgWidgets',
        'PySide6.QtTest', 'PySide6.QtTextToSpeech', 'PySide6.QtUiTools',
        'PySide6.QtWebChannel', 'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineQuick', 'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebSockets', 'PySide6.QtWebView', 'PySide6.QtXml',
        # Other unrelated heavy stuff PyInstaller drags in transitively.
        'numpy', 'PIL', 'pytest', '_pytest', 'setuptools', 'pip',
    ],
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
    name='ContainerTracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app.ico'],
)
