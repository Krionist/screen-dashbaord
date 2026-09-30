import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { map, catchError } from 'rxjs/operators';

export interface DiskInfo {
  mount: string;
  used_gb: number;
  total_gb: number;
  percent: number;
}

export interface MediaInfo {
  active: boolean;
  title?: string;
  artist?: string;
  album?: string;
  playing?: boolean;
  position_s?: number;
  duration_s?: number;
  source?: string;
  has_thumbnail?: boolean;
  thumb_version?: number;
}

export interface SystemMetrics {
  cpuUsage: number;
  cpuTemp: number;
  cpuFreq: number;
  cpuPower: number;
  gpuUsage: number;
  gpuTemp: number;
  gpuFreq: number;
  gpuPower: number;
  gpuMemoryUsage: number;
  gpuMemoryTotal: number;
  ramUsage: number;
  ramTotal: number;
  ramFreq: number;
  motherboardTemp: number;
  fans: { name: string; rpm: number; percent: number }[];
  fps: number;
  refreshRate: number;
  downloadSpeed: string;
  downloadSpeedUnit: string;
  uploadSpeed: string;
  uploadSpeedUnit: string;
  diskRead: string;
  diskWrite: string;
  ramPercent: number;
  pingMs: number | null;
  pingAvg: number | null;
  pingJitter: number;
  pingLoss: number;
  pingRouter: number | null;
  disks: DiskInfo[];
  media: MediaInfo;
  gameMode: boolean;
  fullscreen: boolean;
  windowTitle: string;
  gameName: string;
}

@Injectable({
  providedIn: 'root',
})
export class MetricsService {
  private metricsUrl = '/metrics';

  constructor(private http: HttpClient) {}

  getMetrics(): Observable<{ metrics: SystemMetrics; volume: number }> {
    return this.http.get(this.metricsUrl, { responseType: 'text' }).pipe(
      map((text) => {
        // Replace NaN with 0 before parsing
        const cleanedText = text.replace(/:\s*NaN/g, ':0');
        const data = JSON.parse(cleanedText);
        return {
          metrics: this.parseJsonMetrics(data),
          volume: data.volume_percent || 0,
        };
      }),
      catchError((error) => {
        console.error('Error fetching metrics:', error);
        return of({
          metrics: this.getDefaultMetrics(),
          volume: 0,
        });
      }),
    );
  }

  private parseJsonMetrics(data: any): SystemMetrics {
    const metrics = this.getDefaultMetrics();
    // Helper function to parse values with units and comma decimals
    const parseValue = (value: any): number => {
      if (typeof value === 'number') return value;
      if (typeof value === 'string') {
        // Remove units and replace comma with dot
        const cleaned = value
          .replace(/[°CW%]/g, '')
          .replace(',', '.')
          .trim();
        const parsed = parseFloat(cleaned);
        return isNaN(parsed) ? 0 : parsed;
      }
      return 0;
    };

    // CPU metrics
    metrics.cpuUsage = parseValue(data.cpu_load) || 0;
    metrics.cpuFreq = parseValue(data.cpu_freq_mhz) || 0;

    // Find CPU temp (AMD Ryzen tctl/tdie or package)
    for (const key in data) {
      const lowerKey = key.toLowerCase();
      if (
        lowerKey.includes('ryzen') &&
        lowerKey.includes('temp') &&
        (lowerKey.includes('tctl') || lowerKey.includes('core_(tctl'))
      ) {
        metrics.cpuTemp = parseValue(data[key]);
        break;
      }
    }

    // Find CPU power (AMD Ryzen package power)
    for (const key in data) {
      const lowerKey = key.toLowerCase();
      if (
        lowerKey.includes('ryzen') &&
        lowerKey.includes('power') &&
        lowerKey.includes('package')
      ) {
        metrics.cpuPower = parseValue(data[key]);
        break;
      }
    }

    // GPU metrics
    metrics.gpuUsage = parseValue(data.gpu_load) || 0;
    metrics.gpuTemp = parseValue(data.gpu_temp) || 0;
    metrics.gpuFreq = parseValue(data.gpu_clock_mhz) || 0;
    metrics.gpuPower = parseValue(data.gpu_power_w) || 0;

    // GPU Memory - vram_used_mb and vram_total_mb (convert MB to GB)
    if (data.vram_used_mb) {
      metrics.gpuMemoryUsage = parseValue(data.vram_used_mb) / 1024;
    }
    if (data.vram_total_mb) {
      metrics.gpuMemoryTotal = parseValue(data.vram_total_mb) / 1024;
    }

    // RAM metrics
    metrics.ramUsage = parseValue(data.ram_used_gb) || 0;
    metrics.ramTotal = parseValue(data.ram_total_gb) || 32;

    // Find RAM frequency from LHM data
    for (const key in data) {
      if (key.includes('memory') && key.includes('clock')) {
        metrics.ramFreq = parseValue(data[key]);
        break;
      }
    }

    // Motherboard temp from LHM data (ASUS TUF Gaming B550-Plus)
    for (const key in data) {
      const lowerKey = key.toLowerCase();
      if (
        (lowerKey.includes('asus') ||
          lowerKey.includes('nuvoton') ||
          lowerKey.includes('nct6798d')) &&
        lowerKey.includes('temp') &&
        lowerKey.includes('#1')
      ) {
        metrics.motherboardTemp = parseValue(data[key]);
        break;
      }
    }
    // Network speed - check for both LHM format and direct backend format
    if (data.net_download_mbps !== undefined) {
      metrics.downloadSpeed = data.net_download_mbps.toString();
      metrics.downloadSpeedUnit = 'Mbps';
    } else {
      for (const key in data) {
        const lowerKey = key.toLowerCase();
        if (lowerKey.includes('ethernet_throughput_download_speed')) {
          const value = data[key];
          // Parse value and unit (e.g., "125.5 MB/s" -> value: "125.5", unit: "MB/s")
          if (typeof value === 'string') {
            const match = value.match(/^([\d.]+)\s*(.*)$/);
            if (match) {
              metrics.downloadSpeed = match[1];
              metrics.downloadSpeedUnit = match[2] || 'MB/s';
            }
          }
        }
      }
    }

    if (data.net_upload_mbps !== undefined) {
      metrics.uploadSpeed = data.net_upload_mbps.toString();
      metrics.uploadSpeedUnit = 'Mbps';
    } else {
      for (const key in data) {
        const lowerKey = key.toLowerCase();
        if (lowerKey.includes('ethernet_throughput_upload_speed')) {
          const value = data[key];
          // Parse value and unit
          if (typeof value === 'string') {
            const match = value.match(/^([\d.]+)\s*(.*)$/);
            if (match) {
              metrics.uploadSpeed = match[1];
              metrics.uploadSpeedUnit = match[2] || 'MB/s';
            }
          }
        }
      }
    }

    // Disk read/write speed - check for both direct backend format and LHM format
    if (data.disk_read_mbps !== undefined) {
      metrics.diskRead = data.disk_read_mbps.toString();
    } else {
      for (const key in data) {
        const lowerKey = key.toLowerCase();
        if (lowerKey.includes('disk') && lowerKey.includes('read')) {
          metrics.diskRead = typeof data[key] === 'string' ? data[key] : data[key].toString();
        }
      }
    }

    if (data.disk_write_mbps !== undefined) {
      metrics.diskWrite = data.disk_write_mbps.toString();
    } else {
      for (const key in data) {
        const lowerKey = key.toLowerCase();
        if (lowerKey.includes('disk') && lowerKey.includes('write')) {
          metrics.diskWrite = typeof data[key] === 'string' ? data[key] : data[key].toString();
        }
      }
    }

    // Fallback: any motherboard/chipset temp
    if (metrics.motherboardTemp === 0) {
      for (const key in data) {
        const lowerKey = key.toLowerCase();
        if (
          (lowerKey.includes('motherboard') ||
            lowerKey.includes('mainboard') ||
            lowerKey.includes('chipset')) &&
          lowerKey.includes('temp')
        ) {
          metrics.motherboardTemp = parseValue(data[key]);
          break;
        }
      }
    }

    // Extract fan speeds from LHM data
    const fans: { name: string; rpm: number; percent: number }[] = [];
    for (const key in data) {
      if (key.includes('fan') && !key.includes('control')) {
        const fanName = this.formatFanName(key);
        const rpm = parseValue(data[key]);
        const percent = Math.min((rpm / 2000) * 100, 100);
        fans.push({ name: fanName, rpm, percent });
      }
    }

    if (fans.length > 0) {
      metrics.fans = fans;
    }

    // FPS (if available from PresentMon)
    metrics.fps = parseValue(data.fps) || 0;

    // Refresh rate from backend
    metrics.refreshRate = parseValue(data.refresh_rate) || 144;

    // RAM percent, ping, disks, media, game mode
    metrics.ramPercent = parseValue(data.ram_percent) || 0;
    metrics.pingMs = data.ping_ms ?? null;
    metrics.pingAvg = data.ping_avg_ms ?? null;
    metrics.pingJitter = parseValue(data.ping_jitter_ms) || 0;
    metrics.pingLoss = parseValue(data.ping_loss_pct) || 0;
    metrics.pingRouter = data.ping_router_ms ?? null;
    metrics.disks = Array.isArray(data.disks) ? data.disks : [];
    metrics.media = data.media ?? { active: false };
    metrics.gameMode = !!data.game_mode;
    metrics.fullscreen = !!data.fullscreen;
    metrics.windowTitle = data.window_title ?? '';
    metrics.gameName = data.game_name ?? '';

    return metrics;
  }

  private formatFanName(key: string): string {
    // Keys look like "desktop-xyz_..._nct6798d_fans_fan_#1" or "..._rtx_3090_fans_gpu_fan_2"
    const lower = key.toLowerCase();
    const num = lower.match(/(\d+)$/)?.[1] ?? '';
    const prefix = lower.includes('gpu') ? 'GPU FAN' : 'CASE FAN';
    return `${prefix} ${num}`.trim();
  }

  private getDefaultMetrics(): SystemMetrics {
    return {
      cpuUsage: 0,
      cpuTemp: 0,
      cpuFreq: 0,
      cpuPower: 0,
      gpuUsage: 0,
      gpuTemp: 0,
      gpuFreq: 0,
      gpuPower: 0,
      gpuMemoryUsage: 0,
      gpuMemoryTotal: 8,
      ramUsage: 0,
      ramTotal: 32,
      ramFreq: 0,
      motherboardTemp: 0,
      fans: [
        { name: 'CPU FAN', rpm: 0, percent: 0 },
        { name: 'GPU FANS', rpm: 0, percent: 0 },
        { name: 'CASE FRONT', rpm: 0, percent: 0 },
      ],
      fps: 0,
      refreshRate: 144,
      downloadSpeed: '0',
      downloadSpeedUnit: 'MB/s',
      uploadSpeed: '0',
      uploadSpeedUnit: 'MB/s',
      diskRead: 'NA',
      diskWrite: 'NA',
      ramPercent: 0,
      pingMs: null,
      pingAvg: null,
      pingJitter: 0,
      pingLoss: 0,
      pingRouter: null,
      disks: [],
      media: { active: false },
      gameMode: false,
      fullscreen: false,
      windowTitle: '',
      gameName: '',
    };
  }
}
