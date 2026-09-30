"""
RTSS (RivaTuner Statistics Server) shared memory reader.
Reads FPS data from RTSS shared memory - works with anti-cheat games.
Requires RTSS to be installed and running.
"""
import mmap
import struct
import logging
import time
import threading
from typing import Dict, Any

logger = logging.getLogger(__name__)

RTSS_MEMORY_NAME = "Local\\RTSSSharedMemoryV2"

# Shared memory header: signature, version, appEntrySize, appArrOffset, appArrSize, ...
HEADER_FMT = "<IIIII"  # 5 x DWORD
HEADER_SIZE = struct.calcsize(HEADER_FMT)

# App entry fixed prefix: processID (4), name (260), flags (4), time0 (4), time1 (4), frames (4), frameTime (4)
APP_ENTRY_PREFIX_FMT = "<I260sIIIII"
APP_ENTRY_PREFIX_SIZE = struct.calcsize(APP_ENTRY_PREFIX_FMT)

RTSS_SIGNATURE = 0x52545353  # 'RTSS'


class RTSSClient:
    def __init__(self, poll_interval: float = 0.5):
        self.poll_interval = poll_interval
        self.running = False
        self._lock = threading.Lock()
        self._last_time1: Dict[int, int] = {}  # pid -> last time1
        self._stale_counts: Dict[int, int] = {}  # pid -> unchanged poll count
        self.data: Dict[str, Any] = {
            "fps": 0,
            "frametime_ms": 0.0,
            "process_name": "",
            "available": False,
        }
        self._thread: threading.Thread | None = None

    @property
    def available(self) -> bool:
        return self._is_rtss_running()

    def _is_rtss_running(self) -> bool:
        try:
            mm = mmap.mmap(-1, 4, RTSS_MEMORY_NAME, access=mmap.ACCESS_READ)
            mm.close()
            return True
        except Exception:
            return False

    def _read_shared_memory(self) -> Dict[str, Any]:
        # Read header first to calculate exact needed size
        try:
            mm = mmap.mmap(-1, HEADER_SIZE, RTSS_MEMORY_NAME, access=mmap.ACCESS_READ)
            header_data = mm.read(HEADER_SIZE)
            mm.close()
        except Exception as e:
            logger.debug(f"RTSS not available: {e}")
            return {}

        _, _, app_entry_size, app_arr_offset, app_arr_size = struct.unpack_from(HEADER_FMT, header_data, 0)
        needed = app_arr_offset + app_arr_size * app_entry_size

        try:
            mm = mmap.mmap(-1, needed, RTSS_MEMORY_NAME, access=mmap.ACCESS_READ)
            data = mm.read(needed)
            mm.close()
            result = self._parse(data)
            if result.get("available"):
                logger.debug(f"RTSS: {result['process_name']} {result['fps']} FPS")
            return result
        except Exception as e:
            logger.error(f"RTSS full read failed (need {needed} bytes): {e}")
            return {}

    def _parse(self, data: bytes) -> Dict[str, Any]:
        if len(data) < HEADER_SIZE:
            return {}

        sig, version, app_entry_size, app_arr_offset, app_arr_size = struct.unpack_from(
            HEADER_FMT, data, 0
        )
        logger.debug(f"RTSS header: sig={sig:#x} ver={version} entry_size={app_entry_size} arr_offset={app_arr_offset} arr_size={app_arr_size}")

        if sig != RTSS_SIGNATURE:
            logger.debug(f"RTSS signature mismatch: {sig:#x}")
            return {}

        best = None

        for i in range(app_arr_size):
            offset = app_arr_offset + i * app_entry_size
            if offset + APP_ENTRY_PREFIX_SIZE > len(data):
                break

            pid, name_bytes, flags, time0, time1, frames, frame_time_us = struct.unpack_from(
                APP_ENTRY_PREFIX_FMT, data, offset
            )

            if pid == 0:
                continue

            name = name_bytes.split(b"\x00")[0].decode("utf-8", errors="replace")
            logger.debug(f"RTSS entry: pid={pid} name={name} fps_raw={frame_time_us}")

            # Detect stale data (game exited)
            if time1 == self._last_time1.get(pid, -1):
                self._stale_counts[pid] = self._stale_counts.get(pid, 0) + 1
                if self._stale_counts[pid] >= 3:  # 3 polls without update = game exited
                    continue  # skip stale entries
            else:
                self._last_time1[pid] = time1
                self._stale_counts[pid] = 0

            fps = 0.0
            frametime_ms = 0.0

            if frame_time_us > 0:
                fps = 1_000_000.0 / frame_time_us
                frametime_ms = frame_time_us / 1000.0
            elif time1 > time0 and frames > 0:
                elapsed_ms = time1 - time0
                fps = frames * 1000.0 / elapsed_ms
                frametime_ms = elapsed_ms / frames

            if fps > 0 and (best is None or fps > best["fps"]):
                best = {
                    "fps": round(fps),
                    "frametime_ms": round(frametime_ms, 2),
                    "process_name": name,
                    "available": True,
                }

        return best or {}

    def _poll(self):
        logger.info("RTSS polling started")
        while self.running:
            data = self._read_shared_memory()
            with self._lock:
                if data:
                    self.data.update(data)
                else:
                    self.data["available"] = False
            time.sleep(self.poll_interval)
        logger.info("RTSS polling stopped")

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()
        logger.info("RTSS client started")

    def stop(self):
        self.running = False

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return self.data.copy()
