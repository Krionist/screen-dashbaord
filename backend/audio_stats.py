"""
Audio statistics module using pycaw.
Provides Windows system volume level.
"""
from typing import Dict, Any
import logging

try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False
    logging.warning("pycaw not available - audio volume stats will be disabled")


class AudioStats:
    def __init__(self):
        self.initialized = False
        self.volume_interface = None

        if PYCAW_AVAILABLE:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(
                    IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self.volume_interface = cast(interface, POINTER(IAudioEndpointVolume))
                self.initialized = True
                logging.info("Audio volume monitoring initialized")
            except Exception as e:
                logging.error(f"Failed to initialize audio monitoring: {e}")
                self.initialized = False

    def get_volume_stats(self) -> Dict[str, Any]:
        """Get system volume statistics."""
        if not self.initialized:
            return {
                "audio_available": False,
                "volume_percent": 0,
                "muted": False
            }

        try:
            # Get volume level (0.0 to 1.0)
            volume_level = self.volume_interface.GetMasterVolumeLevelScalar()
            volume_percent = round(volume_level * 100, 0)

            # Get mute status
            muted = self.volume_interface.GetMute()

            return {
                "audio_available": True,
                "volume_percent": volume_percent,
                "muted": bool(muted)
            }

        except Exception as e:
            logging.error(f"Failed to get audio stats: {e}")
            return {
                "audio_available": False,
                "audio_error": str(e),
                "volume_percent": 0,
                "muted": False
            }
