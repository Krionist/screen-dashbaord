import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, interval, startWith, switchMap, shareReplay, catchError, of } from 'rxjs';

export interface RssItem {
  title: string;
  link: string;
  pubDate?: string;
  description?: string;
}

@Injectable({
  providedIn: 'root'
})
export class RssService {
  private readonly REFRESH_INTERVAL = 60 * 1000; // 1 minute (backend caches Reddit for 5 min)
  private readonly API_BASE = ''; // Backend URL (relative)

  private redditRss$ = interval(this.REFRESH_INTERVAL).pipe(
    startWith(0),
    switchMap(() =>
      this.http.get<RssItem[]>(`${this.API_BASE}/rss/reddit`).pipe(catchError(() => of([] as RssItem[]))),
    ),
    shareReplay(1)
  );

  private newsRss$ = interval(this.REFRESH_INTERVAL).pipe(
    startWith(0),
    switchMap(() =>
      this.http.get<RssItem[]>(`${this.API_BASE}/rss/news`).pipe(catchError(() => of([] as RssItem[]))),
    ),
    shareReplay(1)
  );

  constructor(private http: HttpClient) {}

  getRedditRss(): Observable<RssItem[]> {
    return this.redditRss$;
  }

  getNewsRss(): Observable<RssItem[]> {
    return this.newsRss$;
  }
}
