import sys
import ctypes

import bpy


def disable_quick_edit():
    """Disable the Windows console 'QuickEdit Mode' (and Insert Mode).

    QuickEdit makes a stray click in Blender's System Console put the console
    into a text-selection state that *blocks the process on its next stdout
    write*. Because Cycles streams bake progress to stdout from inside the
    native bake call, that block freezes the whole bake (CPU/GPU drop to 0)
    until the selection is cleared. Turning QuickEdit off removes the trap.

    Safe no-op on non-Windows, or when there is no interactive console
    (background/headless bakes, redirected stdout). Never raises.
    """
    if sys.platform != "win32":
        return
    try:
        k32 = ctypes.windll.kernel32
        k32.GetStdHandle.restype = ctypes.c_void_p
        k32.GetStdHandle.argtypes = [ctypes.c_int]
        k32.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
        k32.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_uint]

        STD_INPUT_HANDLE = -10
        ENABLE_EXTENDED_FLAGS = 0x0080
        ENABLE_QUICK_EDIT_MODE = 0x0040
        ENABLE_INSERT_MODE = 0x0020

        handle = k32.GetStdHandle(STD_INPUT_HANDLE)
        if not handle:
            return

        mode = ctypes.c_uint(0)
        if not k32.GetConsoleMode(handle, ctypes.byref(mode)):
            return  # no interactive console attached

        # ENABLE_EXTENDED_FLAGS must be set for the QuickEdit/Insert bits to take effect.
        new_mode = (mode.value & ~ENABLE_QUICK_EDIT_MODE & ~ENABLE_INSERT_MODE) | ENABLE_EXTENDED_FLAGS
        k32.SetConsoleMode(handle, new_mode)
    except Exception:
        pass


def ensure_console_visible():
    """Open Blender's System Console if it's currently hidden, so long blocking
    operations (bake/export) are actually visible.

    wm.console_toggle() is a *toggle*, so we first check the real window state
    via the Win32 console HWND and only toggle when it's hidden -- that way we
    never accidentally close a console you already have open (or an external
    terminal Blender was launched from). No-op off Windows / when no console.
    """
    if sys.platform != "win32":
        return
    try:
        k32 = ctypes.windll.kernel32
        u32 = ctypes.windll.user32
        k32.GetConsoleWindow.restype = ctypes.c_void_p
        u32.IsWindowVisible.argtypes = [ctypes.c_void_p]
        u32.IsWindowVisible.restype = ctypes.c_int

        hwnd = k32.GetConsoleWindow()
        if not hwnd or u32.IsWindowVisible(hwnd):
            return  # no console attached, or it's already visible
    except Exception:
        return

    try:
        if hasattr(bpy.ops.wm, "console_toggle"):
            bpy.ops.wm.console_toggle()
    except Exception:
        pass
