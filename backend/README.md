# PC Bridge - Windows PC Monitoring API

Windows rendszer metrikák HTTP API-n keresztül, dashboard-ok számára (pl. Glance).

## Architektúra

```
LibreHardwareMonitor (admin, háttér)
        │
        │  HTTP :8085/data.json
        ▼
   pc-bridge.py  ◄── psutil, pynvml, pywin32, PresentMon
        │
        │  HTTP :9101/metrics
        ▼
   Dashboard (Kubernetes)
```

## Telepítés

### 1. Python környezet

```bash
# Python 3.8+ szükséges
python -m venv venv
venv\Scripts\activate

# Függőségek telepítése
pip install -r requirements.txt
```

### 2. LibreHardwareMonitor (opcionális, de ajánlott)

- Letöltés: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor
- **Adminisztrátorként kell futtatni**
- Options → Remote Web Server → Enable
- Alapértelmezett port: `8085`
- Ellenőrzés: http://localhost:8085/data.json

### 3. PresentMon (opcionális, FPS-hez)

- Letöltés: https://github.com/GameTechDev/PresentMon
- Helyezd el a PATH-ban vagy a bridge mellett
- Csak akkor szükséges, ha FPS monitoring kell

## Használat

### Alapértelmezett indítás

```bash
python pc-bridge.py
```

Ez elindítja az API-t a `0.0.0.0:9101` címen.

### Opciók

```bash
python pc-bridge.py --help

# Egyéni port
python pc-bridge.py --port 8080

# Csak localhost
python pc-bridge.py --host 127.0.0.1

# PresentMon engedélyezése
python pc-bridge.py --enable-presentmon

# Debug mód
python pc-bridge.py --debug
```

### Windows indítás automatizálása

Használd a `start-bridge.bat` fájlt:

```batch
@echo off
cd /d "%~dp0"

REM Virtuális környezet aktiválása
call venv\Scripts\activate.bat

REM Bridge indítása
python pc-bridge.py

pause
```

## API Végpontok

### Egészség ellenőrzés
```
GET /health
```

Visszaadja a modulok állapotát.

### Összes metrika
```
GET /metrics
```

Visszaadja az összes elérhető metrikát egy JSON objektumban.

Példa válasz:
```json
{
  "cpu_load": 45.2,
  "cpu_freq_mhz": 3600,
  "ram_used_gb": 12.5,
  "ram_total_gb": 32.0,
  "gpu_load": 87,
  "gpu_temp": 72,
  "vram_used_mb": 4096,
  "fps": 144,
  "fullscreen": true,
  ...
}
```

### Specifikus metrikák

```
GET /metrics/system     # CPU, RAM, Network, Disk
GET /metrics/gpu        # GPU load, VRAM, temp, power
GET /metrics/lhm        # LibreHardwareMonitor összes szenzor
GET /metrics/lhm/fans   # Csak ventilátorok
GET /metrics/lhm/temps  # Csak hőmérsékletek
GET /metrics/fps        # FPS és frametime (ha PresentMon enabled)
```

### Konfiguráció

```
GET /config             # Jelenlegi konfiguráció lekérése
POST /config            # Konfiguráció módosítása
```

Példa POST:
```json
{
  "enable_lhm": true,
  "enable_gpu": true,
  "enable_presentmon": false,
  "enable_fullscreen": true
}
```

## Metrikák

### System (psutil)
- `cpu_load` - CPU kihasználtság %
- `cpu_freq_mhz` - CPU frekvencia MHz-ben
- `ram_used_gb` / `ram_total_gb` - RAM használat
- `net_upload_mbps` / `net_download_mbps` - Hálózati sebesség
- `disk_read_mbps` / `disk_write_mbps` - Disk I/O
- `uptime_seconds` - Rendszer uptime

### GPU (pynvml - Nvidia)
- `gpu_load` - GPU kihasználtság %
- `gpu_temp` - GPU hőmérséklet °C
- `vram_used_mb` / `vram_total_mb` - VRAM használat
- `gpu_power_w` - GPU fogyasztás Watt-ban
- `gpu_clock_mhz` - GPU órajel
- `gpu_fan_speed` - Ventilátor %

### LibreHardwareMonitor
- Fan RPM-ek (minden ventilátorhoz)
- Hőmérsékletek (CPU, GPU, Motherboard, stb.)
- Voltages
- További szenzorok dinamikusan

### PresentMon (ha enabled)
- `fps` - Aktuális FPS
- `frametime_ms` - Frame idő milliszekundumban
- `process_name` - Monitorizált alkalmazás

### Fullscreen (pywin32)
- `fullscreen` - Boolean, fullscreen-e az aktív ablak
- `window_title` - Aktív ablak címe

## Troubleshooting

### "GPU not available"
- Ellenőrizd, hogy van-e Nvidia GPU
- Telepítsd az nvidia-ml-py csomagot: `pip install nvidia-ml-py`

### "LHM not available"
- LibreHardwareMonitor fut?
- Adminisztrátorként indítottad?
- Remote Web Server engedélyezve van?
- Elérhető: http://localhost:8085/data.json

### "pywin32 not available"
- Windows-on vagy?
- Telepítsd: `pip install pywin32`
- Futtasd: `python venv\Scripts\pywin32_postinstall.py -install`

### "PresentMon not found"
- Letöltötted?
- PATH-ban van vagy a bridge mellett?
- `--enable-presentmon` kapcsoló használva?

## Windows Task Scheduler beállítása

1. Task Scheduler megnyitása
2. Create Task
3. General tab:
   - "Run whether user is logged on or not"
   - "Run with highest privileges" (LHM-hez)
4. Triggers tab:
   - "At startup" vagy "At log on"
5. Actions tab:
   - Program: `C:\Path\To\Python\python.exe`
   - Arguments: `C:\Path\To\pc-bridge.py`
   - Start in: `C:\Path\To\`

## Glance Dashboard integráció

A Glance dashboard-ba így veheted fel:

```yaml
- type: monitor
  cache: 1s
  title: PC Metrics
  site:
    url: http://YOUR-PC-IP:9101/metrics
  monitors:
    - label: CPU
      value-field: cpu_load
      suffix: "%"
    - label: GPU
      value-field: gpu_load
      suffix: "%"
    - label: RAM
      value-field: ram_percent
      suffix: "%"
```

## Licenc

MIT

## Linkek

- [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor)
- [PresentMon](https://github.com/GameTechDev/PresentMon)
- [psutil](https://psutil.readthedocs.io/)
- [pynvml](https://pypi.org/project/nvidia-ml-py/)
