"""
PresentMon integration for FPS and frametime monitoring.
Runs PresentMon in background, writes to temp file, tails it.
"""
import subprocess
import threading
import logging
import os
import time
from typing import Dict, Any, Optional


class PresentMonMonitor:
    def __init__(self, presentmon_path: str = "PresentMon64.exe"):
        self.presentmon_path = presentmon_path
        self.process: Optional[subprocess.Popen] = None
        self.running = False
        self.output_file: Optional[str] = None
        self.data = {
            "fps": 0,
            "frametime_ms": 0.0,
            "frametime_99th_percentile": 0.0,
            "process_name": "",
            "available": False,
        }
        self._lock = threading.Lock()

    def _check_presentmon_available(self) -> bool:
        if os.path.exists(self.presentmon_path):
            logging.info(f"PresentMon found at {self.presentmon_path}")
            return True

        common_paths = [
            "PresentMon64.exe",
            "PresentMon.exe",
            "./PresentMon64.exe",
            "./PresentMon.exe",
            "C:\\Tools\\PresentMon\\PresentMon64.exe",
        ]
        for path in common_paths:
            if os.path.exists(path):
                self.presentmon_path = path
                logging.info(f"PresentMon found at {path}")
                return True

        logging.warning(f"PresentMon not found at '{self.presentmon_path}' or common locations")
        return False

    def _tail_output_file(self):
        """Tail the PresentMon output file and parse CSV lines."""
        # Wait for file to appear
        for _ in range(20):
            if self.output_file and os.path.exists(self.output_file):
                break
            time.sleep(0.5)
        else:
            logging.error(f"PresentMon output file never appeared: {self.output_file}")
            return

        logging.info(f"Tailing PresentMon output: {self.output_file}")

        header = None
        ms_idx = None
        app_idx = None
        raw_count = 0

        try:
            with open(self.output_file, "r", encoding="utf-8", errors="replace") as f:
                while self.running:
                    line = f.readline()
                    if not line:
                        time.sleep(0.05)
                        continue

                    line = line.strip()
                    if not line:
                        continue

                    if raw_count < 5:
                        logging.info(f"PresentMon raw[{raw_count}]: {line}")
                        raw_count += 1

                    parts = line.split(',')

                    # Detect header row
                    if parts[0] in ("Application", "ProcessName"):
                        header = [h.strip() for h in parts]
                        for candidate in ("msBetweenPresents", "MsBetweenPresents", "ms_between_presents"):
                            if candidate in header:
                                ms_idx = header.index(candidate)
                                break
                        for candidate in ("Application", "ProcessName"):
                            if candidate in header:
                                app_idx = header.index(candidate)
                                break
                        logging.info(f"PresentMon CSV header: {header}")
                        logging.info(f"Column indices: app={app_idx}, msBetweenPresents={ms_idx}")
                        continue

                    if ms_idx is None:
                        continue

                    try:
                        if len(parts) <= ms_idx:
                            continue
                        ms_between_presents = float(parts[ms_idx])
                        process_name = parts[app_idx].strip() if app_idx is not None else ""

                        with self._lock:
                            if ms_between_presents > 0:
                                self.data["fps"] = round(1000.0 / ms_between_presents)
                                self.data["frametime_ms"] = round(ms_between_presents, 2)
                                self.data["process_name"] = process_name
                                self.data["available"] = True

                    except (ValueError, IndexError) as e:
                        logging.debug(f"Failed to parse line: {e} | {line}")

        except Exception as e:
            logging.error(f"PresentMon tail error: {e}")
        finally:
            rc = self.process.poll() if self.process else None
            logging.info(f"PresentMon tail stopped (process exit code: {rc})")

    def start(self):
        if self.running:
            logging.warning("PresentMon already running")
            return

        if not self._check_presentmon_available():
            logging.error("PresentMon not available")
            return

        try:
            # Write to backend directory — easy to inspect, no buffering issues
            self.output_file = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "presentmon_output.csv"
            )
            # Remove existing file so PresentMon creates fresh
            if os.path.exists(self.output_file):
                os.unlink(self.output_file)

            cmd = [
                self.presentmon_path,
                "-output_file", self.output_file,
                "-no_top",
            ]
            logging.info(f"Starting PresentMon: {' '.join(cmd)}")
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            logging.info(f"PresentMon PID: {self.process.pid}, output: {self.output_file}")

            self.running = True

            threading.Thread(target=self._tail_output_file, daemon=True).start()

            def log_stderr():
                for line in iter(self.process.stderr.readline, ''):
                    line = line.strip()
                    if line:
                        logging.warning(f"PresentMon stderr: {line}")
            threading.Thread(target=log_stderr, daemon=True).start()

            logging.info("PresentMon monitoring started")

        except Exception as e:
            logging.error(f"Failed to start PresentMon: {e}")

    def stop(self):
        self.running = False

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

        if self.output_file and os.path.exists(self.output_file):
            try:
                os.unlink(self.output_file)
            except Exception:
                pass
            self.output_file = None

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return self.data.copy()
