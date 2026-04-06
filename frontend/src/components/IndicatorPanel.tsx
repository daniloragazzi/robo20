import { useEffect, useState } from "react";
import { useIndicatorStore } from "@/stores/indicatorStore";
import { useChartStore } from "@/stores/chartStore";
import type { IndicatorInfo } from "@/api/indicators";

const CATEGORIES: Record<string, string[]> = {
  "Trend": ["ema", "sma", "vwap"],
  "Oscillator": ["rsi", "macd", "stoch"],
  "Volatility": ["bbands", "atr"],
  "Volume": ["volume"],
  "Price Action": ["mss", "choch", "fvg", "lateralization", "fibonacci"],
};

export function IndicatorPanel() {
  const {
    available,
    availableLoaded,
    loadAvailable,
    instances,
    loadInstances,
    addInstance,
    removeInstance,
    panelOpen,
    setPanelOpen,
  } = useIndicatorStore();

  const timeframe = useChartStore((s) => s.timeframe);

  const [adding, setAdding] = useState<IndicatorInfo | null>(null);
  const [formParams, setFormParams] = useState<Record<string, unknown>>({});
  const [formTf, setFormTf] = useState(timeframe);
  const [formFollowChart, setFormFollowChart] = useState(true);
  const [formLabel, setFormLabel] = useState("");
  const [formNotify, setFormNotify] = useState(false);

  useEffect(() => {
    if (panelOpen && !availableLoaded) loadAvailable();
    if (panelOpen) loadInstances();
  }, [panelOpen]);

  useEffect(() => setFormTf(timeframe), [timeframe]);

  if (!panelOpen) return null;

  function startAdd(info: IndicatorInfo) {
    setAdding(info);
    // Set defaults from schema
    const defaults: Record<string, unknown> = {};
    for (const [key, def] of Object.entries(info.params_schema.properties)) {
      if (def.default !== undefined) defaults[key] = def.default;
    }
    setFormParams(defaults);
    setFormLabel("");
    setFormNotify(false);
    setFormFollowChart(true);
    setFormTf(timeframe);
  }

  async function handleAdd() {
    if (!adding) return;
    await addInstance({
      indicator_type: adding.name,
      params: formParams,
      timeframe: formFollowChart ? timeframe : formTf,
      follow_chart_tf: formFollowChart,
      label: formLabel || undefined,
      notify_telegram: formNotify,
    });
    setAdding(null);
  }

  return (
    <div className="absolute right-0 top-0 z-50 flex h-full w-80 flex-col border-l border-zinc-800 bg-zinc-950">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
        <span className="text-sm font-semibold">Indicadores</span>
        <button
          onClick={() => setPanelOpen(false)}
          className="text-zinc-400 hover:text-zinc-100"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Active indicators */}
        {instances.length > 0 && (
          <div className="border-b border-zinc-800 px-3 py-2">
            <span className="text-xs font-medium text-zinc-500">ATIVOS</span>
            {instances.map((inst) => (
              <div
                key={inst.id}
                className="mt-1 flex items-center justify-between rounded bg-zinc-900 px-2 py-1.5"
              >
                <div className="flex items-center gap-1.5">
                  {(() => {
                    const p = inst.params as Record<string, unknown>;
                    const c = (p.color ?? p.color_macd ?? p.color_k) as string | undefined;
                    return c ? (
                      <span
                        className="inline-block h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: c }}
                      />
                    ) : null;
                  })()}
                  <span className="text-xs font-medium text-zinc-200">
                    {inst.label || inst.indicator_type.toUpperCase()}
                  </span>
                  <span className="ml-1.5 text-xs text-zinc-500">
                    {inst.follow_chart_tf ? `Auto (${timeframe})` : inst.timeframe}
                  </span>
                </div>
                <button
                  onClick={() => removeInstance(inst.id)}
                  className="text-xs text-zinc-500 hover:text-red-400"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Add — configuration form */}
        {adding && (
          <div className="border-b border-zinc-800 px-3 py-2">
            <span className="text-xs font-medium text-zinc-500">
              CONFIGURAR: {adding.display_name}
            </span>

            {/* Dynamic params */}
            <div className="mt-2 space-y-2">
              {Object.entries(adding.params_schema.properties)
                .filter(([key]) => !key.startsWith("color"))
                .map(([key, def]) => (
                  <label key={key} className="block">
                    <span className="text-xs text-zinc-400">
                      {def.description || key}
                    </span>
                    <input
                      type={def.type === "integer" || def.type === "number" ? "number" : "text"}
                      value={String(formParams[key] ?? "")}
                      onChange={(e) => {
                        const val =
                          def.type === "integer"
                            ? parseInt(e.target.value) || 0
                            : def.type === "number"
                              ? parseFloat(e.target.value) || 0
                              : e.target.value;
                        setFormParams({ ...formParams, [key]: val });
                      }}
                      className="mt-0.5 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-100 outline-none focus:border-zinc-500"
                    />
                  </label>
                ))}

              {/* Color pickers */}
              {Object.entries(adding.params_schema.properties)
                .filter(([key, def]) => key.startsWith("color") && def.type === "string")
                .map(([key, def]) => (
                  <label key={key} className="flex items-center gap-2">
                    <input
                      type="color"
                      value={String(formParams[key] ?? def.default ?? "#ffffff")}
                      onChange={(e) =>
                        setFormParams({ ...formParams, [key]: e.target.value })
                      }
                      className="h-6 w-6 cursor-pointer rounded border border-zinc-700 bg-transparent p-0"
                    />
                    <span className="text-xs text-zinc-400">
                      {def.description || key}
                    </span>
                  </label>
                ))}

              {/* Follow chart TF toggle */}
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={formFollowChart}
                  onChange={(e) => setFormFollowChart(e.target.checked)}
                  className="rounded border-zinc-700"
                />
                <span className="text-xs text-zinc-400">
                  Seguir TF do gráfico
                </span>
              </label>

              {/* Timeframe — only visible when NOT following chart */}
              {!formFollowChart && (
              <label className="block">
                <span className="text-xs text-zinc-400">Timeframe fixo</span>
                <select
                  value={formTf}
                  onChange={(e) => setFormTf(e.target.value)}
                  className="mt-0.5 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-100 outline-none focus:border-zinc-500"
                >
                  {["1m", "5m", "15m", "30m", "1h", "4h", "1d"].map((tf) => (
                    <option key={tf} value={tf}>
                      {tf.toUpperCase()}
                    </option>
                  ))}
                </select>
              </label>
              )}

              {/* Label */}
              <label className="block">
                <span className="text-xs text-zinc-400">Label (opcional)</span>
                <input
                  type="text"
                  value={formLabel}
                  onChange={(e) => setFormLabel(e.target.value)}
                  placeholder={`${adding.display_name} ${formTf}`}
                  className="mt-0.5 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-100 outline-none focus:border-zinc-500"
                />
              </label>

              {/* Telegram notify */}
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={formNotify}
                  onChange={(e) => setFormNotify(e.target.checked)}
                  className="rounded border-zinc-700"
                />
                <span className="text-xs text-zinc-400">
                  Enviar sinal para Telegram
                </span>
              </label>
            </div>

            <div className="mt-3 flex gap-2">
              <button
                onClick={handleAdd}
                className="flex-1 rounded bg-zinc-100 px-2 py-1 text-xs font-medium text-zinc-900 hover:bg-zinc-200"
              >
                Adicionar
              </button>
              <button
                onClick={() => setAdding(null)}
                className="flex-1 rounded border border-zinc-700 px-2 py-1 text-xs text-zinc-400 hover:text-zinc-200"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}

        {/* Indicator library by category */}
        {!adding &&
          Object.entries(CATEGORIES).map(([cat, names]) => {
            const items = available.filter((a) => names.includes(a.name));
            if (!items.length) return null;
            return (
              <div key={cat} className="px-3 py-2">
                <span className="text-xs font-medium text-zinc-500">
                  {cat.toUpperCase()}
                </span>
                <div className="mt-1 space-y-0.5">
                  {items.map((info) => (
                    <button
                      key={info.name}
                      onClick={() => startAdd(info)}
                      className="flex w-full items-center rounded px-2 py-1.5 text-left text-xs text-zinc-300 hover:bg-zinc-800"
                    >
                      {info.display_name}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
}
