# Screen Dashboard (KINETIC HORIZON)

Windows-os PC-statisztika dashboard egy külön kis monitorra (1920×720). Egy Python (Flask) **bridge** gyűjti a gép adatait, egy Angular frontend jeleníti meg egy kiosk Chrome ablakban, ami tálcaikonról vezérelhető.

## Mit tud

- **Rendszer:** CPU/GPU terhelés, hőmérséklet, órajel, teljesítmény, RAM/VRAM, ventilátorok, hálózati és lemezsebesség
- **FPS:** RTSS-ből (valós idejű FPS és frame time)
- **Játék mód:** teljes képernyős játék esetén a dashboard átvált: nagy FPS-számláló (átlag/low/min/max), ping, hőmérséklet-grafikon, teljesítmény és ventilátorok
- **Figyelmeztetések:** sárga/piros sáv magas hőmérsékletnél, tele RAM-nál/VRAM-nál/lemeznél, magas pingnél vagy internetkimaradásnál
- **Hálózati ping:** internet, router, jitter, csomagvesztés
- **Most játszott zene:** a Windows médiavezérlőből (Spotify, böngésző, bármi), borítóképpel
- **Időjárás:** OpenWeatherMap alapján, 3 napos előrejelzéssel
- **Hírek / Reddit:** RSS-ből
- **Tálcaikon:** dashboard megjelenítése/elrejtése, mindig elöl, kilépés

## Felépítés

```
backend/    Flask API + kiosk indító + tálcaikon (Python)
frontend/   Angular 17 dashboard (Tailwind CDN-ről)
```

```
LibreHardwareMonitor ─┐
RTSS (shared memory) ─┼─► backend/pc-bridge.py ──► http://localhost:9101 ──► Chrome kiosk
psutil / NVML / WinRT ┘        (API + statikus frontend)
```

A bridge a lefordított frontendet is kiszolgálja (`frontend/dist/...`), tehát egy folyamat elég.

## Követelmények

- Windows 10/11
- Python 3.11 (a `winsdk` miatt ajánlott ≤ 3.12), Node.js 18+ és npm
- Google Chrome
- NVIDIA GPU a GPU-adatokhoz (`nvidia-ml-py`)
- Opcionális, de ajánlott:
  - [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) – hőmérsékletek, ventilátorok, teljesítmény (Remote Web Server bekapcsolva, port `8085`, adminként futtatva)
  - [RTSS (RivaTuner Statistics Server)](https://www.guru3d.com/pages/rtss-rivatuner-statistics-server-download.html) – FPS
  - [PresentMon](https://github.com/GameTechDev/PresentMon) – alternatív FPS-forrás (`backend/PresentMon64.exe`)

## Telepítés

### 1. Backend

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy config.example.json config.json
```

Szerkeszd a `backend/config.json`-t (ez **nincs** a repóban, csak a példa):

| Kulcs | Jelentés |
| --- | --- |
| `server.host` / `server.port` | Bind cím és port (alapértelmezett: `0.0.0.0:9101`) |
| `lhm.url` | LibreHardwareMonitor JSON címe (`http://localhost:8085/data.json`) |
| `weather.openweathermap_api_key` | [OpenWeatherMap](https://openweathermap.org/api) API-kulcs |
| `weather.lat` / `weather.lon` | A helyszín koordinátái az időjáráshoz |

Az API-kulcs megadható az `OPENWEATHER_API_KEY` környezeti változóval is. Kulcs nélkül a `/weather` 503-at ad, a többi panel működik.

### 2. Frontend

```powershell
cd frontend
npm install
npx ng build
```

A build a `frontend/dist/screen-dashbaord/browser` mappába kerül, ezt szolgálja ki a bridge.

## Futtatás

| Fájl | Mit csinál |
| --- | --- |
| `backend/start-bridge.bat` | Indítás **háttérben**, konzolablak nélkül (`start-bridge-hidden.vbs` → `pythonw`), kiosk Chrome-mal |
| `backend/start-bridge-debug.bat` | Ugyanez látható konzollal, hibakereséshez |
| `backend/start-bridge-no-kiosk.bat` | Csak az API, böngésző nélkül |
| `backend/get-monitors.bat` | Kiírja a monitorok pozícióját és méretét |

Naplófájl: `backend/pc-bridge.log`. Leállítás: tálcaikon → **Kilépés**.

Automatikus indításhoz tegyél egy parancsikont a `start-bridge.bat`-ra a `shell:startup` mappába.

### Kiosk monitor

A kiosk ablak a `--monitor` kapcsolóval választ monitort (alapértelmezés: 2, az alsó 1920×720). A monitorok arányát a `pc-bridge.py` `open_browser_kiosk` függvényében lévő `monitor_configs` írja le; a valódi pozíciót a program a képernyő oldalaránya alapján találja meg, DPI-skálázástól függetlenül. Ha más a monitorod, ott igazítsd.

```powershell
python pc-bridge.py --kiosk --monitor 2
```

## API

| Végpont | Tartalom |
| --- | --- |
| `GET /metrics` | Minden adat egyben (a dashboard ezt kérdezi 2 másodpercenként) |
| `GET /metrics/system` `/gpu` `/lhm` `/fps` | Részadatok |
| `GET /media/thumbnail` | A most játszott szám borítóképe |
| `GET /weather` | OpenWeatherMap proxy (a kulcs nem kerül a böngészőbe) |
| `GET /rss/reddit` `/rss/news` | RSS-hírcsatornák (a Reddit 5 percig gyorsítótárban) |
| `GET /health` | Modulok állapota |
| `GET/POST /config` | Modulok ki/be kapcsolása |

Részletes backend-dokumentáció: [backend/README.md](backend/README.md).

## Fejlesztés

```powershell
cd frontend
npx ng build --watch --configuration development
```

Közben a bridge kiszolgálja az újrafordított fájlokat; egy böngészőben a `http://localhost:9101/` cím megnézhető (a kiosk méretét a DevToolsban 1920×720-ra állítva).

A dashboard elrendezése fix 1920×720. A játék mód észlelése a `backend/fullscreen.py`-ban és a `NON_GAME_PROCESSES` listában (`pc-bridge.py`) állítható: ide kerülnek azok az alkalmazások (böngészők, chat-appok), amelyeket az RTSS mér, de nem játékok.

## Biztonság

- A `backend/config.json` (API-kulcs, koordináták) a `.gitignore`-ban van, ne commitold.
- A bridge alapból `0.0.0.0`-n hallgat, így a helyi hálózatról is elérhető. Ha nem kell, állítsd `127.0.0.1`-re.
