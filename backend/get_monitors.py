"""
Get monitor positions and sizes from Windows.
Run this on Windows to see the exact coordinates.
"""
import sys
import ctypes
from ctypes import wintypes

# Define structures and callbacks
class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

MONITORENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.c_int,
    ctypes.c_ulong,  # HMONITOR
    ctypes.c_ulong,  # HDC
    ctypes.POINTER(RECT),
    ctypes.c_ulong   # LPARAM
)

user32 = ctypes.windll.user32
user32.EnumDisplayMonitors.argtypes = [
    ctypes.c_ulong,
    ctypes.POINTER(RECT),
    MONITORENUMPROC,
    ctypes.c_ulong
]

def get_monitors():
    """Get all monitors with their positions and sizes."""
    monitors = []

    def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        """Callback for EnumDisplayMonitors."""
        rect = lprcMonitor.contents
        monitor_info = {
            "left": rect.left,
            "top": rect.top,
            "right": rect.right,
            "bottom": rect.bottom,
            "width": rect.right - rect.left,
            "height": rect.bottom - rect.top,
        }
        monitors.append(monitor_info)
        return 1

    user32.EnumDisplayMonitors(0, None, MONITORENUMPROC(callback), 0)

    return monitors

def main():
    print("=" * 60)
    print("Monitor Information")
    print("=" * 60)

    monitors = get_monitors()

    for i, monitor in enumerate(monitors, 1):
        print(f"\nMonitor {i}:")
        print(f"  Position: ({monitor['left']}, {monitor['top']})")
        print(f"  Size: {monitor['width']}x{monitor['height']}")
        print(f"  Bounds: ({monitor['left']}, {monitor['top']}) to ({monitor['right']}, {monitor['bottom']})")

    print("\n" + "=" * 60)
    print("For pc-bridge.py monitor_configs, use:")
    print("=" * 60)

    for i, monitor in enumerate(monitors, 1):
        print(f"{i}: {{\"width\": {monitor['width']}, \"height\": {monitor['height']}, \"x\": {monitor['left']}, \"y\": {monitor['top']} }},  # Monitor {i}")

if __name__ == "__main__":
    main()
