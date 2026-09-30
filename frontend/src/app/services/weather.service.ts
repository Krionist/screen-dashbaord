import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { map, catchError } from 'rxjs/operators';

export interface WeatherDay {
  date: string;
  temp: number;
  tempMin: number;
  tempMax: number;
  condition: string;
  icon: string;
  windSpeed?: number;
  windDirection?: number;
  humidity?: number;
  precipitation?: number;
  precipitationProbability?: number;
  feelsLike?: number;
  pressure?: number;
}

export interface WeatherData {
  current: WeatherDay;
  forecast: WeatherDay[];
}

@Injectable({
  providedIn: 'root',
})
export class WeatherService {
  // Derecske coordinates

  constructor(private http: HttpClient) {}

  getWeather(): Observable<WeatherData> {
    // Fetch weather from backend proxy (avoids CORS and SSL issues)
    const backendUrl = '/weather';

    return this.http.get(backendUrl).pipe(
      map((response: any) => this.parseOpenWeatherData(response.current, response.forecast)),
      catchError((error) => {
        console.error('Error fetching weather from backend:', error);
        return of(this.getDefaultWeather());
      })
    );
  }

  private parseOpenWeatherData(data: any, forecastData: any): WeatherData {
    // Map OpenWeatherMap weather codes to icons
    const getIcon = (weatherId: number, icon: string): string => {
      // Weather ID groups: https://openweathermap.org/weather-conditions
      if (weatherId >= 200 && weatherId < 300) return 'thunderstorm'; // Thunderstorm
      if (weatherId >= 300 && weatherId < 400) return 'rainy'; // Drizzle
      if (weatherId >= 500 && weatherId < 600) return 'rainy'; // Rain
      if (weatherId >= 600 && weatherId < 700) return 'ac_unit'; // Snow
      if (weatherId >= 700 && weatherId < 800) return 'foggy'; // Atmosphere (fog, mist, etc)
      if (weatherId === 800) return icon.includes('n') ? 'clear_night' : 'clear_day'; // Clear
      if (weatherId > 800) return 'partly_cloudy_day'; // Clouds
      return 'cloud';
    };

    const weather = data.weather[0];
    const main = data.main;
    const wind = data.wind;

    // Calculate today's min/max from forecast data
    let todayMin = main.temp;
    let todayMax = main.temp;

    if (forecastData && forecastData.list) {
      const today = new Date().toDateString();
      const todayForecasts = forecastData.list.filter((item: any) => {
        const forecastDate = new Date(item.dt * 1000).toDateString();
        return forecastDate === today;
      });

      if (todayForecasts.length > 0) {
        todayMin = Math.min(main.temp, ...todayForecasts.map((item: any) => item.main.temp));
        todayMax = Math.max(main.temp, ...todayForecasts.map((item: any) => item.main.temp));
      }
    }

    const currentWeather: WeatherDay = {
      date: new Date().toLocaleDateString('hu-HU'),
      temp: Math.round(main.temp),
      tempMin: Math.round(todayMin),
      tempMax: Math.round(todayMax),
      condition: weather.description,
      icon: getIcon(weather.id, weather.icon),
      windSpeed: Math.round(wind.speed * 3.6), // m/s to km/h
      windDirection: wind.deg || 0,
      humidity: main.humidity,
      precipitation: 0,
      precipitationProbability: 0,
      feelsLike: Math.round(main.feels_like),
      pressure: main.pressure,
    };

    // Build forecast from forecast data
    const forecast: WeatherDay[] = [];

    if (forecastData && forecastData.list) {
      // Group forecasts by day (skip today)
      const dailyForecasts = new Map<string, any[]>();
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      tomorrow.setHours(0, 0, 0, 0); // start of tomorrow, not 'now + 24h'

      forecastData.list.forEach((item: any) => {
        const forecastDate = new Date(item.dt * 1000);
        const dateKey = forecastDate.toDateString();

        // Skip today's forecasts
        if (forecastDate >= tomorrow) {
          if (!dailyForecasts.has(dateKey)) {
            dailyForecasts.set(dateKey, []);
          }
          dailyForecasts.get(dateKey)!.push(item);
        }
      });

      // Get first 3 days
      let dayCount = 0;
      const dayNames = ['V', 'H', 'K', 'Sze', 'Cs', 'P', 'Szo'];

      for (const [dateKey, items] of dailyForecasts.entries()) {
        if (dayCount >= 3) break;

        const temps = items.map(item => item.main.temp);
        const minTemp = Math.min(...temps);
        const maxTemp = Math.max(...temps);
        const avgTemp = temps.reduce((a, b) => a + b, 0) / temps.length;

        // Use midday forecast for weather condition (around 12:00)
        const middayForecast = items.find(item => {
          const hour = new Date(item.dt * 1000).getHours();
          return hour >= 11 && hour <= 14;
        }) || items[0];

        const forecastDate = new Date(dateKey);
        const dayName = dayCount === 0 ? 'Ho' : dayNames[forecastDate.getDay()];

        forecast.push({
          date: dayName,
          temp: Math.round(avgTemp),
          tempMin: Math.round(minTemp),
          tempMax: Math.round(maxTemp),
          condition: middayForecast.weather[0].description,
          icon: getIcon(middayForecast.weather[0].id, middayForecast.weather[0].icon),
          precipitationProbability: Math.round((middayForecast.pop || 0) * 100),
        });

        dayCount++;
      }
    }

    // Fallback if no forecast data
    if (forecast.length === 0) {
      forecast.push(
        {
          date: 'Ho',
          temp: Math.round(main.temp + 1),
          tempMin: Math.round(todayMin),
          tempMax: Math.round(todayMax + 2),
          condition: weather.description,
          icon: getIcon(weather.id, weather.icon),
          precipitationProbability: 0,
        },
        {
          date: 'Sze',
          temp: Math.round(main.temp),
          tempMin: Math.round(todayMin - 1),
          tempMax: Math.round(todayMax + 1),
          condition: weather.description,
          icon: getIcon(weather.id, weather.icon),
          precipitationProbability: 0,
        },
        {
          date: 'Cs',
          temp: Math.round(main.temp - 1),
          tempMin: Math.round(todayMin - 2),
          tempMax: Math.round(todayMax),
          condition: weather.description,
          icon: getIcon(weather.id, weather.icon),
          precipitationProbability: 0,
        }
      );
    }

    return {
      current: currentWeather,
      forecast,
    };
  }

  private parseWeatherData(data: any): WeatherData {
    const current = data.current;
    const daily = data.daily;

    // Map weather codes to conditions
    const getCondition = (code: number): string => {
      if (code === 0) return 'Clear';
      if (code <= 3) return 'Partly Cloudy';
      if (code <= 48) return 'Foggy';
      if (code <= 67) return 'Rainy';
      if (code <= 77) return 'Snow';
      if (code <= 82) return 'Showers';
      if (code <= 99) return 'Thunderstorm';
      return 'Unknown';
    };

    const getIcon = (code: number): string => {
      if (code === 0) return 'clear_day';
      if (code <= 3) return 'partly_cloudy_day';
      if (code <= 48) return 'foggy';
      if (code <= 67) return 'rainy';
      if (code <= 77) return 'ac_unit';
      if (code <= 82) return 'water_drop';
      if (code <= 99) return 'thunderstorm';
      return 'cloud';
    };

    const getWindDirection = (degrees: number): string => {
      const directions = ['É', 'ÉK', 'K', 'DK', 'D', 'DNY', 'NY', 'ÉNY'];
      const index = Math.round(degrees / 45) % 8;
      return directions[index];
    };

    const currentWeather: WeatherDay = {
      date: new Date().toLocaleDateString('hu-HU'),
      temp: Math.round(current.temperature_2m || 0),
      tempMin: Math.round(daily.temperature_2m_min[0]),
      tempMax: Math.round(daily.temperature_2m_max[0]),
      condition: getCondition(current.weathercode || 0),
      icon: getIcon(current.weathercode || 0),
      windSpeed: Math.round(current.windspeed_10m || 0),
      windDirection: current.winddirection_10m || 0,
      humidity: Math.round(current.relative_humidity_2m || 0),
      precipitation: Math.round((current.precipitation || 0) * 10) / 10,
      precipitationProbability: Math.round(daily.precipitation_probability_max[0] || 0),
      feelsLike: Math.round(current.temperature_2m || 0), // Open-Meteo doesn't provide feels_like
      pressure: Math.round(current.surface_pressure || 0),
    };

    const forecast: WeatherDay[] = [];
    for (let i = 1; i < Math.min(4, daily.time.length); i++) {
      const date = new Date(daily.time[i]);
      forecast.push({
        date: date.toLocaleDateString('hu-HU', { weekday: 'short' }),
        temp: Math.round((daily.temperature_2m_max[i] + daily.temperature_2m_min[i]) / 2),
        tempMin: Math.round(daily.temperature_2m_min[i]),
        tempMax: Math.round(daily.temperature_2m_max[i]),
        condition: getCondition(daily.weathercode[i]),
        icon: getIcon(daily.weathercode[i]),
        precipitationProbability: Math.round(daily.precipitation_probability_max[i] || 0),
      });
    }

    return {
      current: currentWeather,
      forecast,
    };
  }

  private getDefaultWeather(): WeatherData {
    return {
      current: {
        date: new Date().toLocaleDateString('hu-HU'),
        temp: 24,
        tempMin: 20,
        tempMax: 28,
        condition: 'Clear',
        icon: 'clear_day',
        windSpeed: 10,
        windDirection: 180,
        humidity: 65,
        precipitation: 0,
        precipitationProbability: 0,
        feelsLike: 26,
        pressure: 1013,
      },
      forecast: [
        {
          date: 'Holnap',
          temp: 25,
          tempMin: 21,
          tempMax: 29,
          condition: 'Sunny',
          icon: 'clear_day',
          precipitationProbability: 0,
        },
        {
          date: 'Szerda',
          temp: 23,
          tempMin: 19,
          tempMax: 27,
          condition: 'Cloudy',
          icon: 'cloud',
          precipitationProbability: 20,
        },
        {
          date: 'Csütörtök',
          temp: 22,
          tempMin: 18,
          tempMax: 26,
          condition: 'Rainy',
          icon: 'rainy',
          precipitationProbability: 80,
        },
      ],
    };
  }

  getWindDirection(degrees: number): string {
    const directions = ['É', 'ÉK', 'K', 'DK', 'D', 'DNY', 'NY', 'ÉNY'];
    const index = Math.round(degrees / 45) % 8;
    return directions[index];
  }
}
