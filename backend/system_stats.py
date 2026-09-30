"""
System statistics module using psutil.
Provides CPU, RAM, network, disk, and uptime metrics.
"""
import psutil
import time
import ctypes
from typing import Dict, Any


class SystemStats:
    def __init__(self):
        self._last_net_io = None
        self._last_net_time = None
        self._last_disk_io = None
        self._last_disk_time = None

    def get_cpu_stats(self) -> Dict[str, Any]:
        """Get CPU usage and frequency."""
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_freq = psutil.cpu_freq()

        return {
            "cpu_load": round(cpu_percent, 1),
            "cpu_freq_mhz": round(cpu_freq.current, 0) if cpu_freq else 0,
            "cpu_freq_max_mhz": round(cpu_freq.max, 0) if cpu_freq else 0,
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(logical=True),
        }

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get RAM usage statistics."""
        mem = psutil.virtual_memory()

        return {
            "ram_used_gb": round(mem.used / 1024**3, 2),
            "ram_total_gb": round(mem.total / 1024**3, 2),
            "ram_percent": round(mem.percent, 1),
            "ram_available_gb": round(mem.available / 1024**3, 2),
        }

    def get_network_stats(self) -> Dict[str, Any]:
        """Get network I/O statistics with speed calculation."""
        net_io = psutil.net_io_counters()
        current_time = time.time()

        stats = {
            "net_sent_gb": round(net_io.bytes_sent / 1024**3, 2),
            "net_recv_gb": round(net_io.bytes_recv / 1024**3, 2),
            "net_upload_mbps": 0.0,
            "net_download_mbps": 0.0,
        }

        # Calculate speed if we have previous data
        if self._last_net_io and self._last_net_time:
            time_delta = current_time - self._last_net_time
            if time_delta > 0:
                sent_delta = net_io.bytes_sent - self._last_net_io.bytes_sent
                recv_delta = net_io.bytes_recv - self._last_net_io.bytes_recv

                stats["net_upload_mbps"] = round((sent_delta / time_delta) * 8 / 1024**2, 2)
                stats["net_download_mbps"] = round((recv_delta / time_delta) * 8 / 1024**2, 2)

        self._last_net_io = net_io
        self._last_net_time = current_time

        return stats

    def get_disk_stats(self) -> Dict[str, Any]:
        """Get disk usage and I/O statistics."""
        disk_usage = psutil.disk_usage('C:\\')
        disk_io = psutil.disk_io_counters()
        current_time = time.time()

        stats = {
            "disk_used_gb": round(disk_usage.used / 1024**3, 1),
            "disk_total_gb": round(disk_usage.total / 1024**3, 1),
            "disk_percent": round(disk_usage.percent, 1),
            "disk_read_mb": round(disk_io.read_bytes / 1024**2, 1) if disk_io else 0,
            "disk_write_mb": round(disk_io.write_bytes / 1024**2, 1) if disk_io else 0,
            "disk_read_mbps": 0.0,
            "disk_write_mbps": 0.0,
        }

        # Calculate I/O speed if we have previous data
        if self._last_disk_io and self._last_disk_time and disk_io:
            time_delta = current_time - self._last_disk_time
            if time_delta > 0:
                read_delta = disk_io.read_bytes - self._last_disk_io.read_bytes
                write_delta = disk_io.write_bytes - self._last_disk_io.write_bytes

                stats["disk_read_mbps"] = round((read_delta / time_delta) / 1024**2, 2)
                stats["disk_write_mbps"] = round((write_delta / time_delta) / 1024**2, 2)

        self._last_disk_io = disk_io
        self._last_disk_time = current_time

        disks = []
        for part in psutil.disk_partitions(all=False):
            if 'fixed' not in part.opts:
                continue
            try:
                u = psutil.disk_usage(part.mountpoint)
            except Exception:
                continue
            disks.append({
                "mount": part.mountpoint.rstrip("\\"),
                "used_gb": round(u.used / 1024**3, 1),
                "total_gb": round(u.total / 1024**3, 1),
                "percent": round(u.percent, 1),
            })
        stats["disks"] = disks

        return stats

    def get_uptime(self) -> Dict[str, Any]:
        """Get system uptime."""
        uptime_seconds = time.time() - psutil.boot_time()

        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)

        return {
            "uptime_seconds": int(uptime_seconds),
            "uptime_formatted": f"{days}d {hours}h {minutes}m",
        }

    def get_refresh_rate(self) -> Dict[str, Any]:
        """Get display refresh rate (cached; spawning PowerShell on every poll is expensive)."""
        import time
        cached = getattr(self, '_refresh_cache', None)
        if cached and time.time() - cached[0] < 300:
            return cached[1]
        result = self._query_refresh_rate()
        self._refresh_cache = (time.time(), result)
        return result

    def _query_refresh_rate(self) -> Dict[str, Any]:
        try:
            # Try multiple methods to get refresh rate
            import subprocess

            # Method 1: PowerShell query
            try:
                result = subprocess.run(
                    ['powershell', '-Command',
                     'Get-CimInstance -ClassName Win32_DesktopMonitor | Select-Object -ExpandProperty ScreenHeight'],
                    capture_output=True,
                    text=True,
                    timeout=5, stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                # This is indirect, let's try WMI directly
                result = subprocess.run(
                    ['powershell', '-Command',
                     '(Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBasicDisplayParams).ScreenRefreshRate'],
                    capture_output=True,
                    text=True,
                    timeout=5, stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0 and result.stdout.strip():
                    refresh_rate = float(result.stdout.strip())
                    if refresh_rate > 0:
                        return {"refresh_rate": int(refresh_rate)}
            except Exception as e:
                pass

            # Method 2: Try different Windows API approach
            try:
                user32 = ctypes.windll.user32
                # Get primary display device context
                hdc = user32.GetDC(None)
                if hdc:
                    refresh_rate = user32.GetDeviceCaps(hdc, 116)  # VREFRESH
                    user32.ReleaseDC(None, hdc)
                    if refresh_rate > 0:
                        return {"refresh_rate": refresh_rate}
            except Exception as e:
                pass

            # Method 3: Check registry for common refresh rates
            # Fallback to 120Hz as it's more common than 144Hz now
            return {
                "refresh_rate": 120,  # Changed default to 120Hz
            }
        except Exception as e:
            return {
                "refresh_rate": 120,  # Changed default to 120Hz
            }

    def get_all_stats(self) -> Dict[str, Any]:
        """Get all system statistics."""
        stats = {}
        stats.update(self.get_cpu_stats())
        stats.update(self.get_memory_stats())
        stats.update(self.get_network_stats())
        stats.update(self.get_disk_stats())
        stats.update(self.get_uptime())
        stats.update(self.get_refresh_rate())

        return stats
