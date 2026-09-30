"""
Background ping monitor: internet latency, router latency and packet loss.
"""
import logging
import re
import subprocess
import threading
import time
from collections import deque
from typing import Dict, Any, Optional

try:
    import ping3
    ping3.EXCEPTIONS = False
    PING_AVAILABLE = True
except ImportError:
    PING_AVAILABLE = False
    logging.warning("ping3 not available - ping stats disabled")


def _default_gateway() -> Optional[str]:
    try:
        out = subprocess.run(
            ['route', 'print', '-4', '0.0.0.0'],
            capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] == '0.0.0.0' and parts[1] == '0.0.0.0':
                if re.match(r'\d+\.\d+\.\d+\.\d+$', parts[2]):
                    return parts[2]
    except Exception as e:
        logging.warning(f"Could not detect default gateway: {e}")
    return None


class PingMonitor:
    def __init__(self, internet_host: str = '1.1.1.1', interval: float = 2.0):
        self.internet_host = internet_host
        self.interval = interval
        self.gateway = _default_gateway()
        self._internet = deque(maxlen=30)   # ms, or None on loss
        self._router = deque(maxlen=10)
        self._lock = threading.Lock()
        self.available = PING_AVAILABLE
        self._started = False

    def start(self):
        if self._started or not self.available:
            return
        self._started = True
        threading.Thread(target=self._run, daemon=True).start()
        logging.info(f"Ping monitor started (internet={self.internet_host}, router={self.gateway})")

    @staticmethod
    def _ping(host: str) -> Optional[float]:
        try:
            r = ping3.ping(host, timeout=1.5, unit='ms')
            return float(r) if r else None
        except Exception:
            return None

    def _run(self):
        while True:
            inet = self._ping(self.internet_host)
            router = self._ping(self.gateway) if self.gateway else None
            with self._lock:
                self._internet.append(inet)
                self._router.append(router)
            time.sleep(self.interval)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            inet = list(self._internet)
            router = list(self._router)
        ok = [v for v in inet if v is not None]
        last = inet[-1] if inet else None
        jitter = 0.0
        if len(ok) > 1:
            jitter = sum(abs(a - b) for a, b in zip(ok, ok[1:])) / (len(ok) - 1)
        loss = (100.0 * (len(inet) - len(ok)) / len(inet)) if inet else 0.0
        last_router = router[-1] if router else None
        return {
            "ping_ms": round(last, 1) if last is not None else None,
            "ping_avg_ms": round(sum(ok) / len(ok), 1) if ok else None,
            "ping_jitter_ms": round(jitter, 1),
            "ping_loss_pct": round(loss, 0),
            "ping_router_ms": round(last_router, 1) if last_router is not None else None,
            "ping_host": self.internet_host,
        }
