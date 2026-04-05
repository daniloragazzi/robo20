import { create } from "zustand";
import type {
  ChartIndicatorInstance,
  IndicatorDataPoint,
  IndicatorInfo,
} from "@/api/indicators";
import {
  addChartIndicator,
  computeIndicator,
  fetchChartIndicators,
  fetchIndicators,
  removeChartIndicator,
} from "@/api/indicators";

// Indicator data keyed by chart instance id
interface IndicatorData {
  points: IndicatorDataPoint[];
  loading: boolean;
}

interface IndicatorState {
  // Available indicator plugins (from backend registry)
  available: IndicatorInfo[];
  availableLoaded: boolean;
  loadAvailable: () => Promise<void>;

  // Active chart indicator instances (persisted in DB)
  instances: ChartIndicatorInstance[];
  loadInstances: () => Promise<void>;
  addInstance: (body: {
    indicator_type: string;
    params: Record<string, unknown>;
    timeframe: string;
    follow_chart_tf?: boolean;
    label?: string;
    notify_telegram?: boolean;
  }) => Promise<void>;
  removeInstance: (id: number) => Promise<void>;

  // Computed indicator data per instance
  data: Record<number, IndicatorData>;
  computeForInstance: (
    inst: ChartIndicatorInstance,
    symbol: string,
    chartTimeframe: string,
  ) => Promise<void>;

  // Panel open state
  panelOpen: boolean;
  setPanelOpen: (open: boolean) => void;
}

export const useIndicatorStore = create<IndicatorState>((set, get) => ({
  available: [],
  availableLoaded: false,

  loadAvailable: async () => {
    if (get().availableLoaded) return;
    const avail = await fetchIndicators();
    set({ available: avail, availableLoaded: true });
  },

  instances: [],

  loadInstances: async () => {
    const instances = await fetchChartIndicators();
    set({ instances });
  },

  addInstance: async (body) => {
    const inst = await addChartIndicator(body);
    set((s) => ({ instances: [...s.instances, inst] }));
  },

  removeInstance: async (id) => {
    await removeChartIndicator(id);
    set((s) => ({
      instances: s.instances.filter((i) => i.id !== id),
      data: Object.fromEntries(
        Object.entries(s.data).filter(([k]) => Number(k) !== id),
      ),
    }));
  },

  data: {},

  computeForInstance: async (inst, symbol, chartTimeframe) => {
    const effectiveTf = inst.follow_chart_tf ? chartTimeframe : inst.timeframe;
    set((s) => ({
      data: {
        ...s.data,
        [inst.id]: { points: [], loading: true },
      },
    }));
    try {
      const points = await computeIndicator(
        inst.indicator_type,
        symbol,
        effectiveTf,
        inst.params as Record<string, unknown>,
      );
      set((s) => ({
        data: {
          ...s.data,
          [inst.id]: { points, loading: false },
        },
      }));
    } catch {
      set((s) => ({
        data: {
          ...s.data,
          [inst.id]: { points: [], loading: false },
        },
      }));
    }
  },

  panelOpen: false,
  setPanelOpen: (open) => set({ panelOpen: open }),
}));
