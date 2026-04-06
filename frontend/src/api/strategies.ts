const API_BASE = "/api";

// ------------------------------------------------------------------ //
//  Condition tree types                                                //
// ------------------------------------------------------------------ //

export interface ConditionLeafNode {
  type: "condition";
  indicator_type: string;
  condition_type: string;
  condition_value?: string | null;
  output_key?: string | null;
  indicator_ref?: number | null;
}

export interface ConditionGroupNode {
  type: "and" | "or";
  conditions: ConditionNode[];
}

export type ConditionNode = ConditionLeafNode | ConditionGroupNode;

// ------------------------------------------------------------------ //
//  Risk types                                                          //
// ------------------------------------------------------------------ //

export interface PartialExitIn {
  pct: number;
  target_type: string; // "rr_ratio" | "fixed_pct" | "trailing_pct"
  target_value: number;
}

export interface RiskConfigIn {
  stop_loss_type?: string | null;
  stop_loss_value?: number | null;
  take_profit_type?: string | null;
  take_profit_value?: number | null;
  sizing_mode?: string | null; // "fixed_pct" | "risk_based"
  position_size_pct?: number | null;
  risk_pct?: number | null;
  partial_exits?: PartialExitIn[];
}

// ------------------------------------------------------------------ //
//  Strategy types                                                      //
// ------------------------------------------------------------------ //

export interface StrategyIndicatorIn {
  indicator_type: string;
  params: Record<string, unknown>;
  timeframe: string;
  label?: string;
  notify_telegram?: boolean;
}

export interface StrategyStepIn {
  step_index: number;
  indicator_ref?: number | null;
  condition_type?: string | null;
  condition_value?: string | null;
  output_key?: string | null;
  description?: string | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  condition_tree?: Record<string, any> | null;
}

export interface StrategyIn {
  name: string;
  description?: string | null;
  mode: "SINAL_APENAS" | "SEMI_AUTO" | "TOTALMENTE_AUTO";
  indicators: StrategyIndicatorIn[];
  steps: StrategyStepIn[];
  risk_config?: RiskConfigIn | null;
}

export interface StrategyIndicatorOut {
  id: number;
  indicator_type: string;
  params: Record<string, unknown>;
  timeframe: string;
  label: string | null;
  notify_telegram: boolean;
}

export interface StrategyStepOut {
  id: number;
  step_index: number;
  indicator_id: number | null;
  condition_type: string;
  condition_value: string | null;
  condition_tree: ConditionNode | null;
  description: string | null;
}

export interface StrategyOut {
  id: number;
  name: string;
  description: string | null;
  mode: "SINAL_APENAS" | "SEMI_AUTO" | "TOTALMENTE_AUTO";
  indicators: StrategyIndicatorOut[];
  steps: StrategyStepOut[];
  risk_config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface StrategySummary {
  id: number;
  name: string;
  description: string | null;
  mode: "SINAL_APENAS" | "SEMI_AUTO" | "TOTALMENTE_AUTO";
  step_count: number;
  indicator_count: number;
  created_at: string;
  updated_at: string;
}

// ------------------------------------------------------------------ //
//  API functions                                                       //
// ------------------------------------------------------------------ //

export async function fetchStrategies(): Promise<StrategySummary[]> {
  const res = await fetch(`${API_BASE}/strategies/`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export async function fetchStrategy(id: number): Promise<StrategyOut> {
  const res = await fetch(`${API_BASE}/strategies/${id}`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export async function createStrategy(body: StrategyIn): Promise<StrategyOut> {
  const res = await fetch(`${API_BASE}/strategies/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed: ${res.status} — ${text}`);
  }
  return res.json();
}

export async function updateStrategy(id: number, body: StrategyIn): Promise<StrategyOut> {
  const res = await fetch(`${API_BASE}/strategies/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed: ${res.status} — ${text}`);
  }
  return res.json();
}

export async function deleteStrategy(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/strategies/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
}
