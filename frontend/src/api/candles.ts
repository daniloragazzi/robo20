const API_BASE = "/api";

export interface Candle {
  ts: string;
  symbol: string;
  timeframe: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
}

export async function fetchCandles(
  symbol: string,
  timeframe: string = "5m",
  limit: number = 750,
  before?: string,
): Promise<Candle[]> {
  const normalized = symbol.replace("/", "-");
  let url = `${API_BASE}/candles/${normalized}?timeframe=${timeframe}&limit=${limit}`;
  if (before) {
    url += `&before=${encodeURIComponent(before)}`;
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch candles: ${res.status}`);
  return res.json();
}
