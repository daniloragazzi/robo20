import { useEffect, useRef, useState } from "react";

export interface CandleUpdate {
  ts: string;
  symbol: string;
  timeframe: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
}

export function useCandleStream(
  symbol: string,
  timeframe: string,
  onUpdate: (candle: CandleUpdate) => void,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  useEffect(() => {
    const normalized = symbol.replace("/", "-");
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws/candles/${normalized}/${timeframe}`;

    let reconnectTimer: ReturnType<typeof setTimeout>;
    let intentionalClose = false;

    function connect() {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (event) => {
        try {
          const candle: CandleUpdate = JSON.parse(event.data);
          onUpdateRef.current(candle);
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (!intentionalClose) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      intentionalClose = true;
      clearTimeout(reconnectTimer);
      wsRef.current?.close();
      setConnected(false);
    };
  }, [symbol, timeframe]);

  return { connected };
}
