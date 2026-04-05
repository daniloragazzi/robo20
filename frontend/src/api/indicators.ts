const API_BASE = "/api";

export interface IndicatorInfo {
  name: string;
  display_name: string;
  params_schema: {
    type: string;
    properties: Record<string, ParamDef>;
    required?: string[];
  };
}

export interface ParamDef {
  type: string;
  default?: unknown;
  minimum?: number;
  description?: string;
}

export interface IndicatorDataPoint {
  ts: string;
  values: Record<string, number | string | null>;
}

export interface ChartIndicatorInstance {
  id: number;
  indicator_type: string;
  params: Record<string, unknown>;
  timeframe: string;
  follow_chart_tf: boolean;
  label: string | null;
  notify_telegram: boolean;
}

export async function fetchIndicators(): Promise<IndicatorInfo[]> {
  const res = await fetch(`${API_BASE}/indicators/`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export async function computeIndicator(
  indicator: string,
  symbol: string,
  timeframe: string,
  params: Record<string, unknown> = {},
  limit: number = 500,
): Promise<IndicatorDataPoint[]> {
  const res = await fetch(`${API_BASE}/indicators/compute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ indicator, symbol, timeframe, params, limit }),
  });
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export async function fetchChartIndicators(): Promise<ChartIndicatorInstance[]> {
  const res = await fetch(`${API_BASE}/indicators/chart`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export async function addChartIndicator(body: {
  indicator_type: string;
  params: Record<string, unknown>;
  timeframe: string;
  label?: string;
  notify_telegram?: boolean;
}): Promise<ChartIndicatorInstance> {
  const res = await fetch(`${API_BASE}/indicators/chart`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export async function removeChartIndicator(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/indicators/chart/${id}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 204) throw new Error(`Failed: ${res.status}`);
}
