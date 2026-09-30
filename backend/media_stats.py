"""
Now-playing info from the Windows media session (Spotify, browsers, players...) via winsdk.
"""
import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional

try:
    from winsdk.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as SessionManager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
    )
    from winsdk.windows.storage.streams import DataReader
    WINSDK_AVAILABLE = True
except ImportError:
    WINSDK_AVAILABLE = False
    logging.warning("winsdk not available - now playing disabled")


class MediaStats:
    def __init__(self):
        self.available = WINSDK_AVAILABLE
        self._lock = threading.Lock()
        self._info: Dict[str, Any] = {"active": False}
        self._thumb: Optional[bytes] = None
        self._thumb_key = None
        self._thumb_version = 0
        self._started = False

    def start(self):
        if self._started or not self.available:
            return
        self._started = True
        threading.Thread(target=lambda: asyncio.run(self._loop()), daemon=True).start()

    async def _read_thumbnail(self, props) -> Optional[bytes]:
        try:
            ref = props.thumbnail
            if not ref:
                return None
            stream = await ref.open_read_async()
            size = stream.size
            if not size or size > 5_000_000:
                return None
            reader = DataReader(stream)
            await reader.load_async(size)
            buf = bytearray(size)
            reader.read_bytes(buf)
            return bytes(buf)
        except Exception as e:
            logging.debug(f"Thumbnail read failed: {e}")
            return None

    async def _loop(self):
        manager = None
        while True:
            try:
                if manager is None:
                    manager = await SessionManager.request_async()
                session = manager.get_current_session()
                if session is None:
                    with self._lock:
                        self._info = {"active": False}
                else:
                    props = await session.try_get_media_properties_async()
                    playback = session.get_playback_info()
                    timeline = session.get_timeline_properties()
                    playing = playback.playback_status == PlaybackStatus.PLAYING

                    position = timeline.position.total_seconds()
                    duration = (timeline.end_time - timeline.start_time).total_seconds()
                    if playing:
                        try:
                            age = (datetime.now(timezone.utc) - timeline.last_updated_time).total_seconds()
                            position += max(0, min(age, 3600))
                        except Exception:
                            pass
                    if duration > 0:
                        position = min(position, duration)

                    key = (props.title, props.artist, props.album_title)
                    if key != self._thumb_key:
                        thumb = await self._read_thumbnail(props)
                        with self._lock:
                            self._thumb = thumb
                            self._thumb_key = key
                            self._thumb_version += 1

                    with self._lock:
                        self._info = {
                            "active": True,
                            "title": props.title or "",
                            "artist": props.artist or "",
                            "album": props.album_title or "",
                            "playing": playing,
                            "position_s": round(position, 1),
                            "duration_s": round(duration, 1),
                            "source": session.source_app_user_model_id or "",
                            "has_thumbnail": self._thumb is not None,
                            "thumb_version": self._thumb_version,
                        }
            except Exception as e:
                logging.debug(f"Media session poll failed: {e}")
                manager = None
                with self._lock:
                    self._info = {"active": False}
            await asyncio.sleep(1.0)

    def get_info(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._info)

    def get_thumbnail(self) -> Optional[bytes]:
        with self._lock:
            return self._thumb
