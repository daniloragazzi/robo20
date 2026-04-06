import { create } from "zustand";
import type {
  ConditionNode,
  ConditionLeafNode,
  ConditionGroupNode,
  PartialExitIn,
  StrategyIn,
  StrategyIndicatorIn,
  StrategyOut,
  StrategySummary,
  RiskConfigIn,
} from "@/api/strategies";
import {
  createStrategy,
  deleteStrategy,
  fetchStrategies,
  fetchStrategy,
  updateStrategy,
} from "@/api/strategies";

// ------------------------------------------------------------------ //
//  Tree shape converters (API ↔ Frontend)                              //
// ------------------------------------------------------------------ //

/** API returns { op, children } for groups and { indicator_ref, condition_type, threshold } for leaves.
 *  Frontend uses { type: "and"|"or", conditions } for groups and { type: "condition", ... } for leaves. */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function apiTreeToFrontend(node: any): ConditionNode {
  if (node.op && node.children) {
    return {
      type: node.op as "and" | "or",
      conditions: node.children.map(apiTreeToFrontend),
    } as ConditionGroupNode;
  }
  return {
    type: "condition",
    indicator_type: "",
    condition_type: node.condition_type ?? "gt",
    condition_value: node.threshold != null ? String(node.threshold) : node.condition_value ?? null,
    indicator_ref: node.indicator_ref ?? 0,
  } as ConditionLeafNode;
}

function frontendTreeToApi(node: ConditionNode): Record<string, unknown> {
  if (node.type === "condition") {
    const leaf = node as ConditionLeafNode;
    const out: Record<string, unknown> = {
      indicator_ref: leaf.indicator_ref ?? 0,
      condition_type: leaf.condition_type,
    };
    if (leaf.condition_value != null && leaf.condition_value !== "") {
      out.threshold = Number(leaf.condition_value);
    }
    return out;
  }
  const group = node as ConditionGroupNode;
  return {
    op: group.type,
    children: group.conditions.map(frontendTreeToApi),
  };
}

// ------------------------------------------------------------------ //
//  Draft types — used while building a strategy in the UI              //
// ------------------------------------------------------------------ //

export interface DraftIndicator extends StrategyIndicatorIn {
  _key: string; // local unique key for list rendering
}

export interface DraftStep {
  _key: string;
  step_index: number;
  // Legacy flat step (simple condition)
  indicator_ref: number;
  condition_type: string;
  condition_value: string | null;
  output_key: string | null;
  description: string | null;
  // Compound condition tree (takes precedence when set)
  condition_tree: ConditionNode | null;
}

interface StrategyBuilderState {
  // List
  strategies: StrategySummary[];
  listLoading: boolean;
  loadStrategies: () => Promise<void>;

  // Current editing
  editingId: number | null;
  name: string;
  description: string;
  mode: StrategyIn["mode"];
  indicators: DraftIndicator[];
  steps: DraftStep[];
  riskConfig: RiskConfigIn;
  saving: boolean;
  error: string | null;

  // Actions
  resetDraft: () => void;
  setName: (name: string) => void;
  setDescription: (desc: string) => void;
  setMode: (mode: StrategyIn["mode"]) => void;

  addIndicator: (ind: StrategyIndicatorIn) => void;
  removeIndicator: (key: string) => void;
  updateIndicatorParams: (key: string, params: Record<string, unknown>) => void;

  addStep: () => void;
  addGroupStep: (tree: ConditionNode) => void;
  removeStep: (key: string) => void;
  updateStep: (key: string, patch: Partial<DraftStep>) => void;
  moveStep: (fromIdx: number, toIdx: number) => void;

  setRiskConfig: (patch: Partial<RiskConfigIn>) => void;

  // Load existing strategy into editor
  loadForEdit: (id: number) => Promise<void>;

  // Save (create or update)
  save: () => Promise<StrategyOut>;

  // Delete
  remove: (id: number) => Promise<void>;
}

let _keyCounter = 0;
function nextKey() {
  return `k_${++_keyCounter}`;
}

const INITIAL_RISK: RiskConfigIn = {
  stop_loss_type: null,
  stop_loss_value: null,
  take_profit_type: null,
  take_profit_value: null,
  sizing_mode: null,
  position_size_pct: null,
  risk_pct: null,
  partial_exits: [],
};

export const useStrategyStore = create<StrategyBuilderState>((set, get) => ({
  // List
  strategies: [],
  listLoading: false,
  loadStrategies: async () => {
    set({ listLoading: true });
    try {
      const list = await fetchStrategies();
      set({ strategies: list });
    } finally {
      set({ listLoading: false });
    }
  },

  // Editing
  editingId: null,
  name: "",
  description: "",
  mode: "SINAL_APENAS",
  indicators: [],
  steps: [],
  riskConfig: { ...INITIAL_RISK },
  saving: false,
  error: null,

  resetDraft: () =>
    set({
      editingId: null,
      name: "",
      description: "",
      mode: "SINAL_APENAS",
      indicators: [],
      steps: [],
      riskConfig: { ...INITIAL_RISK },
      error: null,
    }),

  setName: (name) => set({ name }),
  setDescription: (description) => set({ description }),
  setMode: (mode) => set({ mode }),

  addIndicator: (ind) =>
    set((s) => ({
      indicators: [...s.indicators, { ...ind, _key: nextKey() }],
    })),
  removeIndicator: (key) =>
    set((s) => {
      const idx = s.indicators.findIndex((i) => i._key === key);
      if (idx < 0) return s;
      // Also remove steps referencing this indicator, and fix refs
      const newIndicators = s.indicators.filter((i) => i._key !== key);
      const newSteps = s.steps
        .filter((step) => step.indicator_ref !== idx)
        .map((step) => ({
          ...step,
          indicator_ref: step.indicator_ref > idx ? step.indicator_ref - 1 : step.indicator_ref,
        }));
      return { indicators: newIndicators, steps: newSteps };
    }),
  updateIndicatorParams: (key, params) =>
    set((s) => ({
      indicators: s.indicators.map((i) =>
        i._key === key ? { ...i, params } : i,
      ),
    })),

  addStep: () =>
    set((s) => ({
      steps: [
        ...s.steps,
        {
          _key: nextKey(),
          step_index: s.steps.length,
          indicator_ref: 0,
          condition_type: "gt",
          condition_value: null,
          output_key: null,
          description: null,
          condition_tree: null,
        },
      ],
    })),
  addGroupStep: (tree) =>
    set((s) => ({
      steps: [
        ...s.steps,
        {
          _key: nextKey(),
          step_index: s.steps.length,
          indicator_ref: 0,
          condition_type: "group",
          condition_value: null,
          output_key: null,
          description: null,
          condition_tree: tree,
        },
      ],
    })),
  removeStep: (key) =>
    set((s) => ({
      steps: s.steps
        .filter((step) => step._key !== key)
        .map((step, i) => ({ ...step, step_index: i })),
    })),
  updateStep: (key, patch) =>
    set((s) => ({
      steps: s.steps.map((step) =>
        step._key === key ? { ...step, ...patch } : step,
      ),
    })),
  moveStep: (fromIdx, toIdx) =>
    set((s) => {
      const arr = [...s.steps];
      const [item] = arr.splice(fromIdx, 1);
      arr.splice(toIdx, 0, item);
      return { steps: arr.map((step, i) => ({ ...step, step_index: i })) };
    }),

  setRiskConfig: (patch) =>
    set((s) => ({ riskConfig: { ...s.riskConfig, ...patch } })),

  loadForEdit: async (id) => {
    const full = await fetchStrategy(id);
    const indicators: DraftIndicator[] = full.indicators.map((ind) => ({
      _key: nextKey(),
      indicator_type: ind.indicator_type,
      params: ind.params,
      timeframe: ind.timeframe,
      label: ind.label ?? undefined,
      notify_telegram: ind.notify_telegram,
    }));
    // Build indicator id → index map
    const idToIdx = new Map(full.indicators.map((ind, i) => [ind.id, i]));
    const steps: DraftStep[] = full.steps.map((s) => ({
      _key: nextKey(),
      step_index: s.step_index,
      indicator_ref: idToIdx.get(s.indicator_id ?? -1) ?? 0,
      condition_type: s.condition_type,
      condition_value: s.condition_value,
      output_key: null,
      description: s.description,
      condition_tree: s.condition_tree ? apiTreeToFrontend(s.condition_tree) : null,
    }));
    set({
      editingId: full.id,
      name: full.name,
      description: full.description ?? "",
      mode: full.mode,
      indicators,
      steps,
      riskConfig: {
        stop_loss_type: (full.risk_config.stop_loss_type as string) ?? null,
        stop_loss_value: (full.risk_config.stop_loss_value as number) ?? null,
        take_profit_type: (full.risk_config.take_profit_type as string) ?? null,
        take_profit_value: (full.risk_config.take_profit_value as number) ?? null,
        sizing_mode: (full.risk_config.sizing_mode as string) ?? null,
        position_size_pct: (full.risk_config.position_size_pct as number) ?? null,
        risk_pct: (full.risk_config.risk_pct as number) ?? null,
        partial_exits: (full.risk_config.partial_exits as PartialExitIn[]) ?? [],
      },
      error: null,
    });
  },

  save: async () => {
    const s = get();
    if (!s.name.trim()) {
      set({ error: "Nome da estratégia é obrigatório" });
      throw new Error("Name required");
    }
    if (s.steps.length === 0) {
      set({ error: "Adicione pelo menos um passo" });
      throw new Error("Steps required");
    }

    const body: StrategyIn = {
      name: s.name.trim(),
      description: s.description.trim() || null,
      mode: s.mode,
      indicators: s.indicators.map((i) => ({
        indicator_type: i.indicator_type,
        params: i.params,
        timeframe: i.timeframe,
        label: i.label,
        notify_telegram: i.notify_telegram ?? false,
      })),
      steps: s.steps.map((step) => {
        if (step.condition_tree) {
          return {
            step_index: step.step_index,
            condition_tree: frontendTreeToApi(step.condition_tree),
            description: step.description,
          };
        }
        return {
          step_index: step.step_index,
          indicator_ref: step.indicator_ref,
          condition_type: step.condition_type,
          condition_value: step.condition_value,
          output_key: step.output_key,
          description: step.description,
        };
      }),
      risk_config: s.riskConfig,
    };

    set({ saving: true, error: null });
    try {
      const result = s.editingId
        ? await updateStrategy(s.editingId, body)
        : await createStrategy(body);
      set({ editingId: result.id, saving: false });
      return result;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Erro ao salvar";
      set({ saving: false, error: msg });
      throw e;
    }
  },

  remove: async (id) => {
    await deleteStrategy(id);
    set((s) => ({
      strategies: s.strategies.filter((st) => st.id !== id),
    }));
  },
}));
