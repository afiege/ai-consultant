import { useRef, useEffect, useCallback, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * WebSocket hook for real-time 6-3-5 brainwriting collaboration.
 *
 * Connects to the backend WS endpoint and dispatches events
 * (session_started, ideas_submitted, round_advanced, session_complete,
 *  ai_ideas_ready, participant_connected, participant_disconnected)
 * so that Step2Page can react immediately instead of relying solely on
 * 3-second polling.
 *
 * Falls back gracefully — the page still polls, so if WS is unavailable
 * nothing breaks.
 */
export function useBrainwritingWs(sessionUuid, participantUuid, handlers = {}) {
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const reconnectDelay = useRef(1000);
  const [connected, setConnected] = useState(false);

  const connect = useCallback(() => {
    if (!sessionUuid || !participantUuid) return;

    // Build WS URL – swap http(s) for ws(s)
    const wsBase = API_BASE_URL.replace(/^http/, 'ws');
    const url = `${wsBase}/api/sessions/${sessionUuid}/six-three-five/ws?participant_uuid=${participantUuid}`;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectDelay.current = 1000; // reset backoff
      };

      ws.onmessage = (msg) => {
        try {
          const { event, data } = JSON.parse(msg.data);
          if (event === 'pong') return; // keep-alive response
          const handler = handlers[event];
          if (typeof handler === 'function') handler(data);
        } catch {
          // Ignore non-JSON messages
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        // Reconnect with exponential backoff (max 30 s)
        reconnectTimer.current = setTimeout(() => {
          reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000);
          connect();
        }, reconnectDelay.current);
      };

      ws.onerror = () => {
        // onclose will fire after onerror — reconnect happens there
        ws.close();
      };
    } catch {
      // WebSocket constructor can throw if URL is invalid
    }
  }, [sessionUuid, participantUuid]); // handlers intentionally excluded – stable ref expected

  // Keep-alive ping every 25 s
  useEffect(() => {
    const id = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping');
      }
    }, 25000);
    return () => clearInterval(id);
  }, []);

  // Connect / disconnect lifecycle
  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on intentional close
        wsRef.current.close();
        wsRef.current = null;
      }
      setConnected(false);
    };
  }, [connect]);

  return { connected };
}
