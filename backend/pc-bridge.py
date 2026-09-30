"""
PC Bridge - Windows PC Monitoring API
Exposes system metrics via HTTP for dashboard consumption.

Usage:
    python pc-bridge.py [--port PORT] [--host HOST]

Requirements:
    - LibreHardwareMonitor running with Remote Web Server enabled (port 8085)
    - Optional: PresentMon for FPS monitoring
"""
import argparse
import json
import logging
import sys
import os
import time
import subprocess
import threading
import requests
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS

from system_stats import SystemStats
from gpu_stats import GPUStats
from lhm_client import LHMClient
from rtss_client import RTSSClient
from fullscreen import FullscreenDetector
from audio_stats import AudioStats
from net_ping import PingMonitor
from media_stats import MediaStats


# Configure logging (to a file, since pythonw has no console)
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pc-bridge.log')
LOG_REDIRECTED = sys.stdout is None or sys.stderr is None
if LOG_REDIRECTED:
    _log_stream = open(LOG_FILE, 'a', encoding='utf-8', buffering=1)
    sys.stdout = sys.stdout or _log_stream
    sys.stderr = sys.stderr or _log_stream
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE, encoding='utf-8')] + ([logging.StreamHandler()] if not LOG_REDIRECTED else [])
)
logger = logging.getLogger(__name__)

# Initialize Flask app with static folder for frontend
FRONTEND_BUILD_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist', 'screen-dashbaord', 'browser')
app = Flask(__name__, static_folder=FRONTEND_BUILD_DIR, static_url_path='')
CORS(app)  # Enable CORS for dashboard access

# Initialize monitoring modules
system_stats = SystemStats()
gpu_stats = GPUStats()
lhm_client = LHMClient()
rtss_client = RTSSClient()
fullscreen_detector = FullscreenDetector()
audio_stats = AudioStats()
ping_monitor = PingMonitor()
media_stats = MediaStats()

# Overlay-hooked apps that are not games (RTSS reports FPS for them too)
NON_GAME_PROCESSES = {
    "chrome.exe", "brave.exe", "msedge.exe", "firefox.exe", "opera.exe", "vivaldi.exe",
    "viber.exe", "discord.exe", "spotify.exe", "slack.exe", "teams.exe", "ms-teams.exe",
    "ferdium.exe", "code.exe", "claude.exe", "telegram.exe", "whatsapp.exe", "obs64.exe",
    "explorer.exe", "steamwebhelper.exe", "electron.exe", "notepad.exe", "cursor.exe",
}

# Configuration
config = {
    "enable_lhm": True,
    "enable_gpu": True,
    "enable_fullscreen": True,
    "enable_audio": True,
}


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "version": "1.0.0",
        "modules": {
            "system": True,
            "gpu": gpu_stats.initialized,
            "lhm": lhm_client.available,
            "rtss": rtss_client.available,
            "fullscreen": fullscreen_detector.available,
            "audio": audio_stats.initialized,
        }
    })


@app.route('/metrics')
def metrics():
    """Main metrics endpoint - returns all available metrics."""
    data = {}

    # System stats (CPU, RAM, Network, Disk)
    try:
        data.update(system_stats.get_all_stats())
    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        data["system_error"] = str(e)

    # GPU stats
    if config["enable_gpu"]:
        try:
            data.update(gpu_stats.get_gpu_stats())
        except Exception as e:
            logger.error(f"Failed to get GPU stats: {e}")
            data["gpu_error"] = str(e)

    # LibreHardwareMonitor sensors
    if config["enable_lhm"]:
        try:
            lhm_data = lhm_client.get_sensors()
            data.update(lhm_data)
        except Exception as e:
            logger.error(f"Failed to get LHM sensors: {e}")
            data["lhm_error"] = str(e)

    # FPS stats via RTSS (always include, 0 if no game running)
    try:
        data.update(rtss_client.get_stats())
    except Exception as e:
        logger.error(f"Failed to get FPS stats: {e}")

    # Fullscreen detection
    if config["enable_fullscreen"]:
        try:
            fullscreen_data = fullscreen_detector.get_stats()
            data.update(fullscreen_data)
        except Exception as e:
            logger.error(f"Failed to get fullscreen status: {e}")
            data["fullscreen_error"] = str(e)

    # Audio volume
    if config["enable_audio"]:
        try:
            audio_data = audio_stats.get_volume_stats()
            data.update(audio_data)
        except Exception as e:
            logger.error(f"Failed to get audio stats: {e}")
            data["audio_error"] = str(e)

    # Game mode: fullscreen non-shell window, or the focused app is what RTSS is measuring
    try:
        rtss_proc = str(data.get("process_name") or "")
        fg_proc = str(data.get("window_process") or "")
        rtss_exe = os.path.basename(rtss_proc).lower()
        rtss_game = (
            data.get("fps", 0) > 0
            and rtss_exe not in NON_GAME_PROCESSES
            and (not fg_proc or os.path.basename(fg_proc).lower() == rtss_exe)
        )
        data["game_mode"] = bool(data.get("game_mode")) or rtss_game
        if data["game_mode"]:
            game_exe = rtss_exe if rtss_game else os.path.basename(fg_proc).lower()
            data["game_name"] = os.path.splitext(game_exe)[0] if game_exe else ""
    except Exception as e:
        logger.error(f"Failed to compute game mode: {e}")

    # Ping / latency
    try:
        data.update(ping_monitor.get_stats())
    except Exception as e:
        logger.error(f"Failed to get ping stats: {e}")

    # Now playing
    try:
        data["media"] = media_stats.get_info()
    except Exception as e:
        logger.error(f"Failed to get media info: {e}")

    return jsonify(data)


@app.route('/media/thumbnail')
def media_thumbnail():
    """Album art / thumbnail of the current media session."""
    img = media_stats.get_thumbnail()
    if not img:
        return ('', 204)
    mime = 'image/png' if img[:4] == b'\x89PNG' else 'image/jpeg'
    return Response(img, mimetype=mime, headers={'Cache-Control': 'no-store'})


@app.route('/metrics/system')
def metrics_system():
    """System metrics only (CPU, RAM, Network, Disk)."""
    try:
        return jsonify(system_stats.get_all_stats())
    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/metrics/gpu')
def metrics_gpu():
    """GPU metrics only."""
    try:
        return jsonify(gpu_stats.get_gpu_stats())
    except Exception as e:
        logger.error(f"Failed to get GPU stats: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/metrics/lhm')
def metrics_lhm():
    """LibreHardwareMonitor sensors only."""
    try:
        return jsonify(lhm_client.get_sensors())
    except Exception as e:
        logger.error(f"Failed to get LHM sensors: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/metrics/lhm/fans')
def metrics_lhm_fans():
    """Fan speed sensors from LHM."""
    try:
        return jsonify(lhm_client.get_fans())
    except Exception as e:
        logger.error(f"Failed to get fan sensors: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/metrics/lhm/temps')
def metrics_lhm_temps():
    """Temperature sensors from LHM."""
    try:
        return jsonify(lhm_client.get_temperatures())
    except Exception as e:
        logger.error(f"Failed to get temperature sensors: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/metrics/fps')
def metrics_fps():
    """FPS and frametime metrics via RTSS."""
    return jsonify(rtss_client.get_stats())


@app.route('/config', methods=['GET', 'POST'])
def get_config():
    """Get or update configuration."""
    global config

    if request.method == 'POST':
        data = request.get_json()

        for key in ['enable_lhm', 'enable_gpu', 'enable_fullscreen']:
            if key in data:
                config[key] = bool(data[key])

        return jsonify({"status": "updated", "config": config})

    return jsonify(config)


def load_file_config():
    """Load backend/config.json (empty dict if missing or invalid)."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    try:
        with open(config_path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


@app.route('/weather')
def get_weather():
    """Proxy weather data from OpenWeatherMap API with forecast."""
    try:
        weather_cfg = load_file_config().get('weather', {})
        lat = weather_cfg.get('lat')
        lon = weather_cfg.get('lon')
        api_key = os.environ.get('OPENWEATHER_API_KEY') or weather_cfg.get('openweathermap_api_key')
        if not api_key or lat is None or lon is None:
            return jsonify({"error": "Weather is not configured: set weather.openweathermap_api_key, "
                                     "weather.lat and weather.lon in backend/config.json"}), 503

        # Get current weather
        current_url = f'https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=hu'
        current_response = requests.get(current_url, timeout=10)
        current_response.raise_for_status()
        current_data = current_response.json()

        # Get 5-day forecast (3-hour intervals)
        forecast_url = f'https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=hu'
        forecast_response = requests.get(forecast_url, timeout=10)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()

        # Combine both responses
        result = {
            'current': current_data,
            'forecast': forecast_data
        }

        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to fetch weather: {e}")
        return jsonify({"error": str(e)}), 500


def parse_rss_xml(xml_content: str, limit: int = 10):
    """Parse RSS XML and return items as list of dicts."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_content)

        logger.info(f"Root tag: {root.tag}, has namespace: {'{' in root.tag}")

        # Handle different RSS formats with namespaces
        items = []

        # Try to find items with different approaches
        # 1. Standard RSS without namespace
        items = root.findall('.//item')

        # 2. Try with common RSS namespaces
        if not items:
            for prefix in ['http://purl.org/rss/1.0/', 'http://www.w3.org/2005/Atom']:
                items = root.findall(f'.//{{{prefix}}}item')
                if items:
                    break

        # 3. Atom feed
        if not items and root.tag.endswith('feed'):
            items = root.findall('.//{http://www.w3.org/2005/Atom}entry')
            if not items:
                # Try without full namespace
                items = root.findall('.//entry')

        # 4. Last resort - find any element named 'item' or 'entry' at any level
        if not items:
            for elem in root.iter():
                if elem.tag.endswith('item') or elem.tag.endswith('entry'):
                    items.append(elem)
                    if len(items) >= limit:
                        break

        logger.info(f"Found {len(items)} items/entries")

        result = []
        for i, item in enumerate(items[:limit]):
            title = ''
            link = ''
            pub_date = ''
            description = ''

            # Get title - try multiple approaches
            title_elem = item.find('title')
            if title_elem is None:
                title_elem = item.find('.//title')
            if title_elem is None:
                title_elem = item.find('{http://www.w3.org/2005/Atom}title')

            if title_elem is not None and title_elem.text:
                title = title_elem.text.strip()

            # Get link
            link_elem = item.find('link')
            if link_elem is None:
                link_elem = item.find('.//link')
            if link_elem is None:
                link_elem = item.find('{http://www.w3.org/2005/Atom}link')

            if link_elem is not None:
                if link_elem.text:
                    link = link_elem.text.strip()
                elif hasattr(link_elem, 'get'):
                    link = link_elem.get('href', '').strip()

            # Get pub date
            for tag in ['pubDate', 'date', 'published', 'updated']:
                pub_date_elem = item.find(tag)
                if pub_date_elem is None:
                    pub_date_elem = item.find('{' + 'http://www.w3.org/2005/Atom' + '}' + tag)
                if pub_date_elem is not None and pub_date_elem.text:
                    pub_date = pub_date_elem.text.strip()
                    break

            # Get description
            for tag in ['description', 'summary', 'content']:
                desc_elem = item.find(tag)
                if desc_elem is None:
                    desc_elem = item.find('{' + 'http://www.w3.org/2005/Atom' + '}' + tag)
                if desc_elem is not None:
                    raw_desc = desc_elem.text or ''
                    # Strip HTML
                    import re
                    description = re.sub(r'<[^>]+>', '', raw_desc)
                    description = description.strip()[:200]
                    break

            if title:  # Only add if we have at least a title
                result.append({
                    'title': title,
                    'link': link,
                    'pubDate': pub_date,
                    'description': description
                })
                logger.info(f"Item {i+1}: {title[:50]}...")

        return result
    except Exception as e:
        logger.error(f"Failed to parse RSS XML: {e}", exc_info=True)
        return []


@app.route('/open-link', methods=['POST'])
def open_link():
    """Open a URL in the default browser (used by the dashboard instead of a Chrome popup)."""
    if request.remote_addr not in ('127.0.0.1', '::1'):
        return jsonify({"error": "local requests only"}), 403
    url = str((request.get_json(silent=True) or {}).get('url', ''))
    if not url.lower().startswith(('http://', 'https://')):
        return jsonify({"error": "only http(s) URLs are allowed"}), 400
    import webbrowser
    webbrowser.open(url)
    return jsonify({"status": "ok"})


reddit_cache = {'data': None, 'time': 0, 'fail': 0}


@app.route('/rss/reddit')
def rss_reddit():
    """Fetch Reddit RSS feed for r/hungary."""
    url = 'https://www.reddit.com/r/hungary.rss'
    try:
        logger.info(f"Fetching Reddit RSS from {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            'Accept-Language': 'hu-HU,hu;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.reddit.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        # Serve from cache if fresh (Reddit rate-limits with 429)
        cached = reddit_cache.get('data')
        if cached and time.time() - reddit_cache['time'] < 300:
            return jsonify(cached)
        if time.time() - reddit_cache.get('fail', 0) < 90:  # back off after a 429
            return jsonify(cached or []), (200 if cached else 503)

        response = None
        last_err = None
        for candidate in (
            'https://www.reddit.com/r/hungary/.rss',
            'https://www.reddit.com/r/hungary.rss',
        ):
            try:
                r = requests.get(candidate, timeout=10, headers=headers)
                r.raise_for_status()
                if not r.text.lstrip().startswith(('<?xml', '<feed', '<rss')):
                    raise requests.exceptions.RequestException('not an RSS/Atom response (login page?)')
                response = r
                break
            except requests.exceptions.RequestException as e:
                last_err = e
                logger.warning(f"Reddit RSS {candidate} failed: {e}")
        if response is None:
            reddit_cache['fail'] = time.time()
            if cached:
                return jsonify(cached)  # stale data is better than an empty panel
            raise last_err
        logger.info(f"Reddit RSS response status: {response.status_code}, length: {len(response.text)}")
        items = parse_rss_xml(response.text, limit=50)  # Get more items to filter
        logger.info(f"Parsed {len(items)} items from Reddit RSS")

        # Sort by date (newest first)
        def parse_date(date_str):
            try:
                from datetime import datetime
                # Reddit uses ISO 8601 format: 2026-04-07T05:57:52+00:00
                dt = datetime.fromisoformat(date_str.replace('+00:00', '+0000').replace('Z', '+0000'))
                return dt.timestamp()
            except Exception as e:
                logger.warning(f"Failed to parse date '{date_str}': {e}")
                return 0

        items.sort(key=lambda x: parse_date(x.get('pubDate', '')), reverse=True)
        logger.info(f"Sorted items, first date: {items[0].get('pubDate') if items else 'N/A'}")

        # Return only top 10
        reddit_cache.update(data=items[:10], time=time.time())
        return jsonify(items[:10])
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching Reddit RSS")
        return jsonify([]), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error fetching Reddit RSS: {e}")
        return jsonify([]), 500
    except Exception as e:
        logger.error(f"Failed to fetch Reddit RSS: {e}", exc_info=True)
        return jsonify([]), 500


@app.route('/rss/news')
def rss_news():
    """Fetch and combine news RSS feeds."""
    urls = [
        'https://telex.hu/rss',
        'https://24.hu/feed/',
        'https://444.hu/feed'
    ]
    try:
        all_items = []
        for url in urls:
            try:
                logger.info(f"Fetching news RSS from {url}")
                response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                response.raise_for_status()
                logger.info(f"News RSS {url} response status: {response.status_code}")
                items = parse_rss_xml(response.text, limit=10)
                logger.info(f"Parsed {len(items)} items from {url}")
                all_items.extend(items)
            except Exception as e:
                logger.error(f"Failed to fetch {url}: {e}", exc_info=True)
                continue

        logger.info(f"Total items before sorting: {len(all_items)}")

        # Sort by date
        def parse_date(date_str):
            try:
                from email.utils import parsedate_to_datetime
                return parsedate_to_datetime(date_str).timestamp()
            except:
                return 0

        all_items.sort(key=lambda x: parse_date(x.get('pubDate', '')), reverse=True)

        logger.info(f"Returning {len(all_items[:15])} news items")
        return jsonify(all_items[:15])
    except Exception as e:
        logger.error(f"Failed to fetch news RSS: {e}", exc_info=True)
        return jsonify([]), 500


# Serve frontend static files
@app.route('/')
def serve_index():
    """Serve the Angular frontend index.html."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    """Serve static files or index.html for Angular routes."""
    file_path = os.path.join(app.static_folder, path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return send_from_directory(app.static_folder, path)
    else:
        # For Angular routes, serve index.html
        return send_from_directory(app.static_folder, 'index.html')


def open_browser_kiosk(url, port, monitor=3):
    """Open Chrome browser in kiosk mode on specified monitor."""
    logger.info(f"Waiting 3 seconds for Flask to start...")
    time.sleep(3)  # Wait for Flask to start

    # Common Chrome browser locations
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
    ]

    chrome_exe = None
    for path in chrome_paths:
        if os.path.exists(path):
            chrome_exe = path
            logger.info(f"Found Chrome at: {path}")
            break

    if not chrome_exe:
        logger.error("Chrome browser not found! Skipping auto-open.")
        logger.error(f"Searched paths: {chrome_paths}")
        return

    # Monitor configuration - exact coordinates from Windows
    monitor_configs = {
        1: {"width": 1080, "height": 2560, "x": -1080, "y": 0},    # Left vertical
        2: {"width": 1920, "height": 720, "x": 869, "y": 2160},    # Bottom
        3: {"width": 2560, "height": 1440, "x": 0, "y": 0},        # Center (main)
    }

    if monitor not in monitor_configs:
        logger.error(f"Monitor {monitor} not configured!")
        return

    config = monitor_configs[monitor]
    monitor_width = config["width"]
    monitor_height = config["height"]
    target_x = config["x"]
    target_y = config["y"]

    dashboard_url = f"http://localhost:{port}/"

    # Use dedicated profile for dashboard to avoid conflicts with existing Chrome windows
    profile_dir = os.path.join(os.path.dirname(__file__), "chrome-dashboard-profile")

    # Start Chrome at position 0,0 first (visible), then move it
    args = [
        chrome_exe,
        f"--user-data-dir={profile_dir}",
        f"--app={dashboard_url}",
        f"--window-size={monitor_width},{monitor_height}",
        "--kiosk",
        "--disable-translate",
        "--disable-features=Translate,TranslateUI,TranslateRecentTarget",
        "--disable-infobars",
        "--disable-session-crashed-bubble",
        "--noerrdialogs",
        "--disable-suggestions-ui",
        "--disable-save-password-bubble",
        "--disable-restore-session-state",
        "--no-first-run",
        "--disable-background-mode",
        "--disable-extensions"
    ]

    try:
        logger.info(f"Opening Chrome browser for monitor {monitor}")
        logger.info(f"Target position: x={target_x}, y={target_y}")
        logger.info(f"Size: {monitor_width}x{monitor_height}")

        import ctypes, win32gui, win32con, win32api
        # Work in physical pixels: otherwise Windows DPI scaling shifts/resizes the window
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
        # Pick the real monitor whose aspect ratio matches the configured one
        want = monitor_width / monitor_height
        best = None
        for _h, _dc, (l, t, r, b) in win32api.EnumDisplayMonitors():
            diff = abs((r - l) / (b - t) - want)
            if best is None or diff < best[0]:
                best = (diff, l, t, r - l, b - t)
        if best and best[0] < 0.05:
            _, target_x, target_y, monitor_width, monitor_height = best
            logger.info(f"Matched monitor at ({target_x}, {target_y}) {monitor_width}x{monitor_height}")

        def chrome_windows():
            found = set()
            def cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd) == "Chrome_WidgetWin_1":
                    found.add(hwnd)
            win32gui.EnumWindows(cb, None)
            return found

        existing = chrome_windows()
        subprocess.Popen(args)

        # Find the window that Chrome just created (never touches the focused window)
        hwnd = None
        for _ in range(40):
            time.sleep(0.5)
            new_windows = chrome_windows() - existing
            if new_windows:
                hwnd = next(iter(new_windows))
                break
        if not hwnd:
            logger.error("Could not find the new Chrome window")
            return

        time.sleep(1)
        # Chrome --kiosk gives true fullscreen; move it onto the target monitor via Win32
        # (no F11 / SendKeys, which would hit whatever window happens to be focused)
        # Hide from taskbar / Alt+Tab (tray icon controls it instead)
        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
        ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                               (ex | win32con.WS_EX_TOOLWINDOW) & ~win32con.WS_EX_APPWINDOW)
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, target_x, target_y,
                              monitor_width, monitor_height,
                              win32con.SWP_SHOWWINDOW)
        dashboard_state['hwnd'] = hwnd
        dashboard_state['topmost'] = True
        dashboard_state['rect'] = (target_x, target_y, monitor_width, monitor_height)
        logger.info(f"Chrome window {hwnd} placed at ({target_x}, {target_y}) {monitor_width}x{monitor_height}")

    except Exception as e:
        logger.error(f"Failed to open browser: {e}", exc_info=True)


dashboard_state = {'hwnd': None, 'topmost': True, 'rect': None}


def _set_dashboard_topmost(on):
    import win32gui, win32con
    hwnd = dashboard_state['hwnd']
    if not hwnd or not win32gui.IsWindow(hwnd):
        return
    x, y, w, h = dashboard_state['rect']
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST if on else win32con.HWND_NOTOPMOST,
                          x, y, w, h, win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE)
    dashboard_state['topmost'] = on


def start_tray():
    """Tray icon: show/hide dashboard, always-on-top toggle, quit."""
    try:
        import pystray
        import win32gui, win32con
        from PIL import Image, ImageDraw
    except ImportError as e:
        logger.warning(f"Tray icon disabled ({e})")
        return

    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 8, 60, 48), 6, fill=(20, 24, 40, 255), outline=(0, 220, 255, 255), width=3)
    d.rectangle((12, 30, 20, 40), fill=(0, 220, 255, 255))
    d.rectangle((26, 20, 34, 40), fill=(0, 220, 255, 255))
    d.rectangle((40, 26, 48, 40), fill=(0, 220, 255, 255))
    d.rectangle((24, 52, 40, 56), fill=(0, 220, 255, 255))

    def toggle_visible(icon, item):
        hwnd = dashboard_state['hwnd']
        if hwnd and win32gui.IsWindow(hwnd):
            if win32gui.IsWindowVisible(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            else:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
                _set_dashboard_topmost(dashboard_state['topmost'])

    def toggle_topmost(icon, item):
        _set_dashboard_topmost(not dashboard_state['topmost'])

    def quit_all(icon, item):
        hwnd = dashboard_state['hwnd']
        if hwnd and win32gui.IsWindow(hwnd):
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        icon.stop()
        gpu_stats.cleanup() if gpu_stats.initialized else None
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem('Dashboard megjelenítése / elrejtése', toggle_visible, default=True),
        pystray.MenuItem('Mindig elöl', toggle_topmost, checked=lambda item: dashboard_state['topmost']),
        pystray.MenuItem('Kilépés', quit_all),
    )
    pystray.Icon('pc-bridge', img, 'PC Bridge Dashboard', menu).run_detached()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='PC Bridge - Windows PC Monitoring API')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=9101, help='Port to listen on (default: 9101)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--kiosk', action='store_true', help='Open Brave browser in kiosk mode on monitor 3')
    parser.add_argument('--monitor', type=int, default=2, help='Monitor number for kiosk mode (default: 2 - bottom 1920x720)')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load config.json if present
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    file_config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                file_config = json.load(f)
            logger.info(f"Loaded config from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load config.json: {e}")

    # Merge: CLI args override config.json
    server_cfg = file_config.get('server', {})
    host = args.host if args.host != '0.0.0.0' else server_cfg.get('host', args.host)
    port = args.port if args.port != 9101 else server_cfg.get('port', args.port)

    # Start RTSS client (always, it's lightweight)
    rtss_client.start()
    ping_monitor.start()
    media_stats.start()

    # Log module status
    logger.info("=" * 60)
    logger.info("PC Bridge - Windows PC Monitoring API")
    logger.info("=" * 60)
    logger.info(f"System monitoring: Enabled")
    logger.info(f"GPU monitoring: {'Enabled' if gpu_stats.initialized else 'Disabled (no GPU or pynvml)'}")
    logger.info(f"LHM monitoring: {'Enabled' if lhm_client.available else 'Disabled (LHM not running)'}")
    logger.info(f"RTSS FPS: {'Enabled' if rtss_client.available else 'Disabled (RTSS not running)'}")
    logger.info(f"Fullscreen detection: {'Enabled' if fullscreen_detector.available else 'Disabled (no pywin32)'}")
    logger.info("=" * 60)
    logger.info(f"Starting server on {host}:{port}")
    logger.info(f"Metrics endpoint: http://{host}:{port}/metrics")
    if args.kiosk:
        logger.info(f"Kiosk mode: Will open Brave on monitor {args.monitor}")
    logger.info("=" * 60)

    # Start browser in kiosk mode if requested (in separate thread)
    if args.kiosk:
        browser_thread = threading.Thread(
            target=open_browser_kiosk,
            args=(f"http://localhost:{port}", port, args.monitor),
            daemon=True
        )
        browser_thread.start()

    start_tray()

    try:
        app.run(host=host, port=port, debug=args.debug)
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        if gpu_stats.initialized:
            gpu_stats.cleanup()
        logger.info("Cleanup complete")
        sys.exit(0)


if __name__ == '__main__':
    main()
