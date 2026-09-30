import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MetricsService, SystemMetrics } from '../services/metrics.service';
import { WeatherService, WeatherData } from '../services/weather.service';
import { RssService, RssItem } from '../services/rss.service';
import { interval, Subscription } from 'rxjs';

export interface DashboardAlert {
  level: 'warn' | 'crit';
  icon: string;
  text: string;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit, OnDestroy {
  currentTime = '';
  currentDate = '';
  weatherData: WeatherData = {
    current: {
      date: '',
      temp: 24,
      tempMin: 20,
      tempMax: 28,
      condition: 'Clear',
      icon: 'clear_day',
    },
    forecast: [],
  };
  volume = 0;

  redditRssItems: RssItem[] = [];
  newsRssItems: RssItem[] = [];

  metrics: SystemMetrics = {
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
    fans: [],
    fps: 0,
    refreshRate: 0,
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

  // Game mode (with hysteresis so it does not flicker)
  gameMode = false;
  private gameOnPolls = 0;
  private gameOffPolls = 0;

  // Alerts
  alerts: DashboardAlert[] = [];
  hasCritical = false;

  // Now playing interpolation
  private mediaPolledAt = Date.now();

  fpsBars: number[] = [];
  private subscriptions: Subscription[] = [];

  // Historical data for line charts (last 50 data points)
  private readonly MAX_DATA_POINTS = 50;
  fpsHistory: number[] = [];
  downloadSpeedHistory: number[] = [];
  uploadSpeedHistory: number[] = [];
  diskReadHistory: number[] = [];
  diskWriteHistory: number[] = [];
  cpuTempHistory: number[] = [];
  gpuTempHistory: number[] = [];
  pingHistory: number[] = [];

  constructor(
    private metricsService: MetricsService,
    private weatherService: WeatherService,
    private rssService: RssService
  ) {}

  ngOnInit() {
    this.updateTime();
    this.updateDate();

    // Update time every second
    const timeSubscription = interval(1000).subscribe(() => {
      this.updateTime();
    });
    this.subscriptions.push(timeSubscription);

    // Update metrics every 2 seconds
    const metricsSubscription = interval(2000).subscribe(() => {
      this.loadMetrics();
    });
    this.subscriptions.push(metricsSubscription);

    // Update weather every 10 minutes
    const weatherSubscription = interval(600000).subscribe(() => {
      this.loadWeather();
    });
    this.subscriptions.push(weatherSubscription);

    // Initial load
    this.loadMetrics();
    this.loadWeather();
    this.loadRss();
  }

  ngOnDestroy() {
    this.subscriptions.forEach((sub) => sub.unsubscribe());
  }

  private updateTime() {
    const now = new Date();
    this.currentTime = now.toLocaleTimeString('hu-HU', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  private updateDate() {
    const now = new Date();
    this.currentDate = now.toLocaleDateString('hu-HU', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  }

  private loadMetrics() {
    this.metricsService.getMetrics().subscribe((data) => {
      this.metrics = data.metrics;
      // Update volume from backend if available
      if (data.volume !== undefined) {
        this.volume = data.volume;
      } else {
        this.volume = 0; // Fallback if backend doesn't provide
      }

      this.mediaPolledAt = Date.now();

      // Update historical data
      this.updateHistoricalData();
      this.updateGameMode();
      this.updateAlerts();
    });
  }

  private loadWeather() {
    this.weatherService.getWeather().subscribe((data) => {
      this.weatherData = data;
    });
  }

  private loadRss() {
    this.rssService.getRedditRss().subscribe((items) => {
      this.redditRssItems = items;
    });

    this.rssService.getNewsRss().subscribe((items) => {
      this.newsRssItems = items;
    });
  }

  formatRssDate(dateStr?: string): string {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 60) return `${diffMins}p`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}ó`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}n`;
  }

  openLink(url: string): void {
    // Open in the system default browser (via the bridge) instead of a Chrome app popup
    fetch('/open-link', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    }).catch(() => window.open(url, '_blank'));
  }

  getWindDirection(degrees: number): string {
    return this.weatherService.getWindDirection(degrees);
  }

  getTempColor(temp: number): string {
    if (temp >= 70) return '#ef4444'; // red
    if (temp >= 55) return '#eab308'; // yellow
    return '#22c55e'; // green
  }

  getWeatherTempColor(temp: number): string {
    if (temp < 0) return '#1e3a8a'; // dark blue (negatív)
    if (temp < 10) return '#60a5fa'; // light blue (0-10)
    if (temp < 25) return '#e5e7eb'; // white/light gray (10-25)
    if (temp < 35) return '#fbbf24'; // yellow (25-35)
    return '#ef4444'; // red (35+)
  }

  getWindSpeedColor(speed: number): string {
    // Beaufort skála alapján (km/h)
    if (speed < 6) return '#22c55e'; // green (szélcsend)
    if (speed < 12) return '#84cc16'; // light green (gyenge szellő)
    if (speed < 20) return '#eab308'; // yellow (közepes szellő)
    if (speed < 39) return '#f97316'; // orange (élénk szél)
    if (speed < 62) return '#ef4444'; // red (erős szél)
    return '#991b1b'; // dark red (viharos szél)
  }

  private updateHistoricalData() {
    // Add new data points
    this.fpsHistory.push(this.metrics.fps);
    this.downloadSpeedHistory.push(this.parseSpeed(this.metrics.downloadSpeed));
    this.uploadSpeedHistory.push(this.parseSpeed(this.metrics.uploadSpeed));
    this.diskReadHistory.push(this.parseSpeed(this.metrics.diskRead));
    this.diskWriteHistory.push(this.parseSpeed(this.metrics.diskWrite));

    this.cpuTempHistory.push(this.metrics.cpuTemp);
    this.gpuTempHistory.push(this.metrics.gpuTemp);
    this.pingHistory.push(this.metrics.pingMs ?? 0);
    for (const h of [this.cpuTempHistory, this.gpuTempHistory, this.pingHistory]) {
      if (h.length > this.MAX_DATA_POINTS) h.shift();
    }

    // Keep only last MAX_DATA_POINTS
    if (this.fpsHistory.length > this.MAX_DATA_POINTS) {
      this.fpsHistory.shift();
      this.downloadSpeedHistory.shift();
      this.uploadSpeedHistory.shift();
      this.diskReadHistory.shift();
      this.diskWriteHistory.shift();
    }
  }

  private parseSpeed(speedStr: string | number): number {
    if (!speedStr || speedStr === 'NA') return 0;
    // If it's already a number, return it
    if (typeof speedStr === 'number') return speedStr;
    // Extract number from strings like "125.5 MB/s" or "1.2 GB/s"
    const match = speedStr.match(/(\d+\.?\d*)/);
    return match ? parseFloat(match[1]) : 0;
  }

  getCircleOffset(percentage: number): number {
    const circumference = 2 * Math.PI * 78; // Updated for larger circles
    return circumference - (percentage / 100) * circumference;
  }

  getMemoryBlocks(): number[] {
    const blocks = 12;
    const usedBlocks = Math.ceil(
      (this.metrics.ramUsage / this.metrics.ramTotal) * blocks,
    );
    return Array(blocks)
      .fill(0)
      .map((_, i) => (i < usedBlocks ? 1 : 0));
  }

  getGpuMemoryBlocks(): number[] {
    const blocks = 12;
    const usedBlocks = Math.ceil(
      (this.metrics.gpuMemoryUsage / this.metrics.gpuMemoryTotal) * blocks,
    );
    return Array(blocks)
      .fill(0)
      .map((_, i) => (i < usedBlocks ? 1 : 0));
  }

  // Generate SVG path for line chart
  generateLinePath(data: number[], width: number, height: number): string {
    if (data.length < 2) return '';

    const max = Math.max(...data, 1); // Prevent division by zero
    const min = Math.min(...data, 0);
    const range = max - min || 1;

    // Calculate step width
    const stepX = width / (data.length - 1);

    // Generate path points
    const points = data.map((value, index) => {
      const x = index * stepX;
      const normalized = (value - min) / range;
      const y = height - normalized * height; // Flip Y axis
      return { x, y };
    });

    // Create smooth path using lines
    let path = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
      path += ` L ${points[i].x} ${points[i].y}`;
    }

    return path;
  }

  // ---------- Game mode ----------
  private updateGameMode() {
    const active = this.metrics.gameMode;
    if (active) {
      this.gameOnPolls++;
      this.gameOffPolls = 0;
      if (this.gameOnPolls >= 2) this.gameMode = true;
    } else {
      this.gameOffPolls++;
      this.gameOnPolls = 0;
      if (this.gameOffPolls >= 6) this.gameMode = false;
    }
  }

  get activeFans() {
    return this.metrics.fans.filter((f) => f.rpm > 0);
  }

  get gameTitle(): string {
    return this.metrics.windowTitle || this.metrics.gameName || 'Fullscreen alkalmazás';
  }

  private activeFps(): number[] {
    return this.fpsHistory.filter((f) => f > 0);
  }

  get frameTime(): string {
    return this.metrics.fps > 0 ? (1000 / this.metrics.fps).toFixed(1) : '-';
  }

  get fpsAvg(): number {
    const v = this.activeFps();
    return v.length ? v.reduce((a, b) => a + b, 0) / v.length : 0;
  }

  get fpsMin(): number {
    const v = this.activeFps();
    return v.length ? Math.min(...v) : 0;
  }

  get fpsMax(): number {
    const v = this.activeFps();
    return v.length ? Math.max(...v) : 0;
  }

  /** Average of the lowest ~5% samples (short history, so the 1% low is approximated). */
  get fpsLow(): number {
    const v = [...this.activeFps()].sort((a, b) => a - b);
    if (v.length < 3) return v.length ? v[0] : 0;
    const n = Math.max(1, Math.round(v.length * 0.05));
    return v.slice(0, n).reduce((a, b) => a + b, 0) / n;
  }

  // ---------- Alerts ----------
  private updateAlerts() {
    const m = this.metrics;
    const list: DashboardAlert[] = [];
    const add = (level: 'warn' | 'crit', icon: string, text: string) =>
      list.push({ level, icon, text });

    if (m.cpuTemp >= 90) add('crit', 'device_thermostat', `CPU ${m.cpuTemp.toFixed(0)}°C`);
    else if (m.cpuTemp >= 80) add('warn', 'device_thermostat', `CPU ${m.cpuTemp.toFixed(0)}°C`);

    if (m.gpuTemp >= 87) add('crit', 'device_thermostat', `GPU ${m.gpuTemp.toFixed(0)}°C`);
    else if (m.gpuTemp >= 80) add('warn', 'device_thermostat', `GPU ${m.gpuTemp.toFixed(0)}°C`);

    if (m.motherboardTemp >= 70) add('warn', 'developer_board', `Alaplap ${m.motherboardTemp.toFixed(0)}°C`);

    if (m.ramPercent >= 95) add('crit', 'memory', `RAM ${m.ramPercent.toFixed(0)}%`);
    else if (m.ramPercent >= 90) add('warn', 'memory', `RAM ${m.ramPercent.toFixed(0)}%`);

    const vramPct = m.gpuMemoryTotal ? (m.gpuMemoryUsage / m.gpuMemoryTotal) * 100 : 0;
    if (vramPct >= 97) add('crit', 'memory_alt', `VRAM ${vramPct.toFixed(0)}%`);
    else if (vramPct >= 92) add('warn', 'memory_alt', `VRAM ${vramPct.toFixed(0)}%`);

    for (const d of m.disks) {
      if (d.percent >= 95) add('crit', 'hard_drive', `${d.mount} lemez ${d.percent.toFixed(0)}%`);
      else if (d.percent >= 90) add('warn', 'hard_drive', `${d.mount} lemez ${d.percent.toFixed(0)}%`);
    }

    if (m.pingLoss >= 100) {
      add('crit', 'wifi_off', 'Nincs internet');
    } else {
      if (m.pingLoss >= 5) add('warn', 'network_ping', `Csomagvesztés ${m.pingLoss.toFixed(0)}%`);
      if (m.pingMs !== null && m.pingMs >= 100) add('warn', 'network_ping', `Ping ${m.pingMs.toFixed(0)} ms`);
    }

    this.alerts = list;
    this.hasCritical = list.some((a) => a.level === 'crit');
  }

  // ---------- Ping ----------
  getPingColor(ping: number | null): string {
    if (ping === null) return '#ef4444';
    if (ping < 30) return '#22c55e';
    if (ping < 70) return '#eab308';
    return '#ef4444';
  }

  // ---------- Disks ----------
  getDiskColor(percent: number): string {
    if (percent >= 90) return 'linear-gradient(90deg,#ef4444,#f87171)';
    if (percent >= 75) return 'linear-gradient(90deg,#eab308,#fde047)';
    return 'linear-gradient(90deg,#00deec,#8ff5ff)';
  }

  formatSize(gb: number): string {
    return gb >= 1000 ? `${(gb / 1024).toFixed(2)} TB` : `${gb.toFixed(0)} GB`;
  }

  // ---------- Now playing ----------
  get mediaPosition(): number {
    const m = this.metrics.media;
    if (!m.active) return 0;
    let pos = m.position_s ?? 0;
    if (m.playing) pos += (Date.now() - this.mediaPolledAt) / 1000;
    const dur = m.duration_s ?? 0;
    return dur > 0 ? Math.min(pos, dur) : pos;
  }

  get mediaProgress(): number {
    const dur = this.metrics.media.duration_s ?? 0;
    return dur > 0 ? (this.mediaPosition / dur) * 100 : 0;
  }

  formatTime(seconds: number): string {
    const s = Math.max(0, Math.floor(seconds));
    const m = Math.floor(s / 60);
    return `${m}:${(s % 60).toString().padStart(2, '0')}`;
  }

  // ---------- Charts ----------
  /** Path with a fixed value range (for temperatures). */
  generateFixedPath(data: number[], width: number, height: number, min: number, max: number): string {
    if (data.length < 2) return '';
    const stepX = width / (data.length - 1);
    const range = max - min || 1;
    return data
      .map((v, i) => {
        const y = height - ((Math.min(Math.max(v, min), max) - min) / range) * height;
        return `${i === 0 ? 'M' : 'L'} ${i * stepX} ${y}`;
      })
      .join(' ');
  }

  yForValue(value: number, height: number, min: number, max: number): number {
    return height - ((value - min) / (max - min || 1)) * height;
  }
}
