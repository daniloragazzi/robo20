import { useState, useCallback, useEffect, type KeyboardEvent } from "react";
import { useChartStore } from "@/stores/chartStore";

export function SymbolSelector() {
  const symbol = useChartStore((s) => s.symbol);
  const setSymbol = useChartStore((s) => s.setSymbol);
  const [input, setInput] = useState(symbol);

  // Sync input when store changes externally
  useEffect(() => {
    setInput(symbol);
  }, [symbol]);

  const handleSubmit = useCallback(() => {
    const normalized = input.trim().toUpperCase().replace("-", "/");
    if (normalized && normalized !== symbol) {
      setSymbol(normalized);
    }
  }, [input, symbol, setSymbol]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Enter") handleSubmit();
    },
    [handleSubmit],
  );

  return (
    <input
      value={input}
      onChange={(e) => setInput(e.target.value)}
      onKeyDown={handleKeyDown}
      onBlur={handleSubmit}
      className="w-36 rounded border border-zinc-700 bg-zinc-900 px-2.5 py-1 text-sm text-zinc-100 outline-none focus:border-zinc-500"
      placeholder="BTC/USDT"
    />
  );
}
