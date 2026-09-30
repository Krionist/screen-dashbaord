"""
GPU statistics module using pynvml (nvidia-ml-py).
Provides Nvidia GPU metrics: load, VRAM, temperature, power, clocks.
"""
from typing import Dict, Any, Optional
import logging

try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    logging.warning("pynvml not available - GPU stats will be disabled")


class GPUStats:
    def __init__(self, device_index: int = 0):
        self.device_index = device_index
        self.handle = None
        self.initialized = False

        if PYNVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self.handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)
                self.initialized = True
                logging.info(f"GPU monitoring initialized for device {device_index}")
            except Exception as e:
                logging.error(f"Failed to initialize GPU monitoring: {e}")
                self.initialized = False

    def get_gpu_name(self) -> str:
        """Get GPU name."""
        if not self.initialized:
            return "N/A"
        try:
            return pynvml.nvmlDeviceGetName(self.handle)
        except Exception as e:
            logging.error(f"Failed to get GPU name: {e}")
            return "Unknown"

    def get_gpu_stats(self) -> Dict[str, Any]:
        """Get comprehensive GPU statistics."""
        if not self.initialized:
            return {
                "gpu_available": False,
                "gpu_name": "N/A",
            }

        try:
            # Utilization
            util = pynvml.nvmlDeviceGetUtilizationRates(self.handle)

            # Memory
            mem = pynvml.nvmlDeviceGetMemoryInfo(self.handle)

            # Temperature
            temp = pynvml.nvmlDeviceGetTemperature(self.handle, pynvml.NVML_TEMPERATURE_GPU)

            # Power
            try:
                power_mw = pynvml.nvmlDeviceGetPowerUsage(self.handle)
                power_w = power_mw / 1000.0
            except Exception:
                power_w = 0.0

            # Clock speeds
            try:
                gpu_clock = pynvml.nvmlDeviceGetClockInfo(self.handle, pynvml.NVML_CLOCK_GRAPHICS)
                mem_clock = pynvml.nvmlDeviceGetClockInfo(self.handle, pynvml.NVML_CLOCK_MEM)
            except Exception:
                gpu_clock = 0
                mem_clock = 0

            # Fan speed (if available)
            try:
                fan_speed = pynvml.nvmlDeviceGetFanSpeed(self.handle)
            except Exception:
                fan_speed = 0

            # Power limit
            try:
                power_limit = pynvml.nvmlDeviceGetPowerManagementLimit(self.handle) / 1000.0
            except Exception:
                power_limit = 0.0

            return {
                "gpu_available": True,
                "gpu_name": self.get_gpu_name(),
                "gpu_load": util.gpu,
                "gpu_memory_load": util.memory,
                "vram_used_mb": round(mem.used / 1024**2, 0),
                "vram_total_mb": round(mem.total / 1024**2, 0),
                "vram_percent": round((mem.used / mem.total) * 100, 1),
                "gpu_temp": temp,
                "gpu_power_w": round(power_w, 1),
                "gpu_power_limit_w": round(power_limit, 1),
                "gpu_clock_mhz": gpu_clock,
                "gpu_mem_clock_mhz": mem_clock,
                "gpu_fan_speed": fan_speed,
            }

        except Exception as e:
            logging.error(f"Failed to get GPU stats: {e}")
            return {
                "gpu_available": False,
                "gpu_error": str(e),
            }

    def cleanup(self):
        """Cleanup NVML resources."""
        if self.initialized:
            try:
                pynvml.nvmlShutdown()
            except Exception as e:
                logging.error(f"Failed to shutdown NVML: {e}")
