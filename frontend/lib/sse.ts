/**
 * Server-Sent Events (SSE) wrapper for negotiation transcript streaming.
 *
 * Connects to `GET /api/v1/negotiations/{session_id}/stream` using the
 * native {@link EventSource} API.
 *
 * ## Reconnection strategy
 * - Exponential backoff: 1s → 2s → 4s → … capped at 30s.
 * - On each successful reconnect, fires `onTranscriptRefresh` so the store
 *   can re-fetch the full transcript from the REST endpoint.
 * - Calls `onEvent` for every inbound SSE message event.
 * - Calls `onStatus` for negotiation status lifecycle updates (RESOLVED, etc.).
 */

const INITIAL_BACKOFF_MS = 1_000;
const MAX_BACKOFF_MS = 30_000;

export interface SSEMessage {
  /** Event type from the SSE `event` field (e.g. "message", "status"). */
  type: string;
  /** Parsed JSON payload, or raw string if unparseable. */
  data: unknown;
}

export interface SSEConnection {
  /** Close the EventSource permanently (no reconnect). */
  close: () => void;
}

/**
 * Connect to an SSE stream for a negotiation session.
 *
 * @param sessionId  UUID of the negotiation session.
 * @param onEvent    Called for every inbound message event (parsed JSON).
 * @param onStatus   Called when the backend sends a `status` event
 *                   (e.g. RESOLVED → client closes gracefully).
 * @param onTranscriptRefresh Called after a successful reconnect —
 *                   the store should re-fetch the full transcript.
 * @param onError    Called on connection errors (optional).
 */
export function connectNegotiationStream(
  sessionId: string,
  onEvent: (msg: SSEMessage) => void,
  onStatus: (status: string) => void,
  onTranscriptRefresh: () => void,
  onError?: (err: Event) => void,
): SSEConnection {
  let backoff = INITIAL_BACKOFF_MS;
  let es: EventSource | null = null;
  let closed = false;

  const url = `/api/v1/negotiations/${sessionId}/stream`;

  function createEventSource(): EventSource {
    const source = new EventSource(url);

    source.addEventListener("message", (event: MessageEvent) => {
      let data: unknown;
      try {
        data = JSON.parse(event.data);
      } catch {
        data = event.data;
      }
      onEvent({ type: "message", data });
    });

    source.addEventListener("status", (event: MessageEvent) => {
      const status = String(event.data).trim();
      onStatus(status);

      // Terminal states — no further events expected
      const terminal = new Set([
        "RESOLVED",
        "REJECTED",
        "FAILED",
        "WITHDRAWN",
        "EXPIRED",
      ]);
      if (terminal.has(status)) {
        closed = true;
        source.close();
      }
    });

    source.onerror = () => {
      if (closed) return;
      es = null;
      if (onError) onError(new Event("error"));
    };

    source.onopen = () => {
      // Reset backoff on successful connection
      backoff = INITIAL_BACKOFF_MS;
      // Signal store to re-fetch the transcript
      onTranscriptRefresh();
    };

    return source;
  }

  function reconnect() {
    if (closed) return;
    setTimeout(() => {
      if (closed || es !== null) return;
      es = createEventSource();
      backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
    }, backoff);
  }

  // Listen for EventSource error events at the window level to trigger reconnects
  const errorHandler = () => {
    if (es === null && !closed) reconnect();
  };
  window.addEventListener("sse-reconnect", errorHandler);

  // Start the initial connection
  es = createEventSource();

  // Hook the actual EventSource error via a polling-like proxy.
  // Native EventSource fires its own onerror; we listen to that via the
  // source's onerror handler above, and then dispatch a custom event
  // to trigger our reconnection logic.
  const originalError = es.onerror;
  if (es) {
    es.onerror = (ev) => {
      if (originalError) originalError.call(es, ev);
      if (!closed) {
        es = null;
        reconnect();
      }
    };
  }

  return {
    close: () => {
      closed = true;
      if (es) {
        es.close();
        es = null;
      }
      window.removeEventListener("sse-reconnect", errorHandler);
    },
  };
}
