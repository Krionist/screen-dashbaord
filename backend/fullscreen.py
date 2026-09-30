"""
Fullscreen detection for Windows using pywin32.
Detects if the foreground window is running in fullscreen mode.
"""
import logging
from typing import Dict, Any

try:
    import win32gui
    import win32con
    import win32api
    import win32process
    import psutil
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    logging.warning("pywin32 not available - fullscreen detection disabled")


# Windows that cover the screen but are not games
NON_GAME_CLASSES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",  # desktop / taskbar
    "Chrome_WidgetWin_1", "MozillaWindowClass",                        # browsers / Electron apps
    "ApplicationFrameWindow", "CabinetWClass",                         # UWP host, Explorer
}


class FullscreenDetector:
    def __init__(self):
        self.available = PYWIN32_AVAILABLE

    def is_fullscreen(self) -> bool:
        """
        Check if the foreground window is in fullscreen mode.
        Returns True if a window covers the entire screen.
        """
        if not self.available:
            return False

        try:
            # Get the foreground window
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return False

            # Get window style
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)

            # Get window rectangle
            rect = win32gui.GetWindowRect(hwnd)
            window_width = rect[2] - rect[0]
            window_height = rect[3] - rect[1]

            # Get screen dimensions
            screen_width = win32api.GetSystemMetrics(0)   # SM_CXSCREEN
            screen_height = win32api.GetSystemMetrics(1)  # SM_CYSCREEN

            # Check if window covers entire screen
            # Allow small margin for taskbar auto-hide
            margin = 5
            is_fullscreen = (
                window_width >= screen_width - margin and
                window_height >= screen_height - margin
            )

            return is_fullscreen

        except Exception as e:
            logging.error(f"Error detecting fullscreen: {e}")
            return False

    def get_foreground_window_info(self) -> Dict[str, Any]:
        """Get information about the foreground window."""
        if not self.available:
            return {
                "fullscreen": False,
                "window_title": "",
                "available": False,
            }

        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return {
                    "fullscreen": False,
                    "window_title": "",
                    "available": True,
                }

            # Get window title
            window_title = win32gui.GetWindowText(hwnd)

            # Get window class
            try:
                window_class = win32gui.GetClassName(hwnd)
            except Exception:
                window_class = ""

            # Get window dimensions
            rect = win32gui.GetWindowRect(hwnd)
            window_width = rect[2] - rect[0]
            window_height = rect[3] - rect[1]

            fullscreen = self.is_fullscreen()
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                window_process = psutil.Process(pid).exe()
            except Exception:
                window_process = ""
            return {
                "window_process": window_process,
                "fullscreen": fullscreen,
                "game_mode": bool(fullscreen and window_class not in NON_GAME_CLASSES and window_title),
                "window_title": window_title,
                "window_class": window_class,
                "window_width": window_width,
                "window_height": window_height,
                "available": True,
            }

        except Exception as e:
            logging.error(f"Error getting window info: {e}")
            return {
                "fullscreen": False,
                "window_title": "",
                "available": False,
                "error": str(e),
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get fullscreen detection stats for API."""
        return self.get_foreground_window_info()
