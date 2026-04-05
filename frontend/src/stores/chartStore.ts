import { create } from "zustand";

interface ChartState {
  symbol: string;
  timeframe: string;
  setSymbol: (s: string) => void;
  setTimeframe: (tf: string) => void;
}

export const useChartStore = create<ChartState>((set) => ({
  symbol: "BTC/USDT",
  timeframe: "5m",
  setSymbol: (symbol) => set({ symbol }),
  setTimeframe: (timeframe) => set({ timeframe }),
}));
