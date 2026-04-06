import { useEffect } from "react";
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from "react-router-dom";
import { Chart } from "@/components/Chart";
import { TimeframeSelector } from "@/components/TimeframeSelector";
import { SymbolSelector } from "@/components/SymbolSelector";
import { IndicatorPanel } from "@/components/IndicatorPanel";
import { StrategyList } from "@/components/StrategyList";
import { StrategyBuilder } from "@/components/StrategyBuilder";
import { useChartStore } from "@/stores/chartStore";
import { useIndicatorStore } from "@/stores/indicatorStore";

function AppShell() {
  const symbol = useChartStore((s) => s.symbol);
  const panelOpen = useIndicatorStore((s) => s.panelOpen);
  const setPanelOpen = useIndicatorStore((s) => s.setPanelOpen);
  const loadAvailable = useIndicatorStore((s) => s.loadAvailable);
  const loadInstances = useIndicatorStore((s) => s.loadInstances);
  const navigate = useNavigate();
  const location = useLocation();

  const isChartPage = location.pathname === "/" || location.pathname === "";
  const isStrategyPage = location.pathname.startsWith("/strategies");

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

        {/* Nav tabs */}
        <button
          onClick={() => navigate("/")}
          className={`rounded px-3 py-1 text-xs font-medium transition ${
            isChartPage
              ? "bg-zinc-700 text-white"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          Chart
        </button>
        <button
          onClick={() => navigate("/strategies")}
          className={`rounded px-3 py-1 text-xs font-medium transition ${
            isStrategyPage
              ? "bg-zinc-700 text-white"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          Estratégias
        </button>

        <div className="h-5 w-px bg-zinc-700" />

        {/* Chart-specific controls — only show on chart page */}
        {isChartPage && (
          <>
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
          </>
        )}

        <span className="ml-auto text-xs text-zinc-500">{symbol}</span>
      </header>

      {/* Content */}
      <main className="flex flex-1 overflow-hidden">
        <Routes>
          <Route
            path="/"
            element={
              <>
                <div className="flex-1 overflow-hidden">
                  <Chart />
                </div>
                {panelOpen && (
                  <aside className="w-80 shrink-0 overflow-y-auto border-l border-zinc-800">
                    <IndicatorPanel />
                  </aside>
                )}
              </>
            }
          />
          <Route path="/strategies" element={<div className="w-full overflow-y-auto"><StrategyList /></div>} />
          <Route path="/strategies/:id" element={<div className="w-full overflow-y-auto"><StrategyBuilder /></div>} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}

export default App;
