import { useEffect } from "react";
import { Chart } from "@/components/Chart";
import { TimeframeSelector } from "@/components/TimeframeSelector";
import { SymbolSelector } from "@/components/SymbolSelector";
import { IndicatorPanel } from "@/components/IndicatorPanel";
import { useChartStore } from "@/stores/chartStore";
import { useIndicatorStore } from "@/stores/indicatorStore";

function App() {
  const symbol = useChartStore((s) => s.symbol);
  const panelOpen = useIndicatorStore((s) => s.panelOpen);
  const setPanelOpen = useIndicatorStore((s) => s.setPanelOpen);
  const loadAvailable = useIndicatorStore((s) => s.loadAvailable);
  const loadInstances = useIndicatorStore((s) => s.loadInstances);

  useEffect(() => {
    loadAvailable();
    loadInstances();
  }, [loadAvailable, loadInstances]);

  return (
    <div className="flex h-screen flex-col bg-zinc-950 text-zinc-100">
      {/* Top bar */}
      <header className="flex items-center gap-4 border-b border-zinc-800 px-4 py-2">
        <h1 className="text-lg font-bold tracking-tight">Robo 2.0</h1>
        <div className="h-5 w-px bg-zinc-700" />
        <SymbolSelector />
        <TimeframeSelector />
        <button
          onClick={() => setPanelOpen(!panelOpen)}
          className={`rounded px-3 py-1 text-xs font-medium transition ${
            panelOpen
              ? "bg-indigo-600 text-white"
              : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
          }`}
        >
          Indicators
        </button>
        <span className="ml-auto text-xs text-zinc-500">{symbol}</span>
      </header>

      {/* Chart + indicator panel */}
      <main className="flex flex-1 overflow-hidden">
        <div className="flex-1 overflow-hidden">
          <Chart />
        </div>
        {panelOpen && (
          <aside className="w-80 shrink-0 overflow-y-auto border-l border-zinc-800">
            <IndicatorPanel />
          </aside>
        )}
      </main>
    </div>
  );
}

export default App;
