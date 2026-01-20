import { Injectable, NgZone } from '@angular/core';
import { Observable, Subject } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';
import { AuthService } from '../common/services/auth.service';

export interface AdkEvent {
  author: string;
  content: {
    parts: { text: string }[];
  };
  // Add other fields as needed based on backend Event model
}

@Injectable({
  providedIn: 'root'
})
export class AgentEventService {
  private eventSource: EventSource | null = null;
  private eventSubject = new Subject<AdkEvent>();

  constructor(
    private authService: AuthService,
    private zone: NgZone
  ) { }

  /**
   * Connects to the SSE stream.
   */
  connect(): void {
    if (this.eventSource) {
      return; // Already connected
    }

    // We need to get the token
    this.authService.getValidFirebaseToken$().subscribe({
      next: (token: string) => {
        if (!token) {
          console.error('AgentEventService: No token received.');
          return;
        }

        // Construct URL with query param for auth
        // Note: backendURL usually includes /api, check environment.ts
        // environment.backendURL is 'http://localhost:8080/api'
        const url = `${environment.backendURL}/agents/events/stream?token=${token}`;

        console.log('Connecting to Agent Event Stream:', url);
        this.eventSource = new EventSource(url);

        this.eventSource.onmessage = (event) => {
          this.zone.run(() => {
            try {
              console.log('SSE Event received:', event.data);
              const parsed = JSON.parse(event.data);
              this.eventSubject.next(parsed);
            } catch (e) {
              console.error('Error parsing SSE event:', e);
            }
          });
        };

        this.eventSource.onerror = (error) => {
          this.zone.run(() => {
            console.error('SSE Error:', error);
            // Handle reconnection or error state
            this.disconnect();
          });
        };
      },
      error: (err) => {
        console.error('AgentEventService: Failed to get valid token for stream connection.', err);
      }
    });
  }

  getEvents(): Observable<AdkEvent> {
    return this.eventSubject.asObservable();
  }

  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}
