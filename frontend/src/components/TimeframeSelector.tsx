import { useChartStore } from "@/stores/chartStore";

const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"];

export function TimeframeSelector() {
  const timeframe = useChartStore((s) => s.timeframe);
  const setTimeframe = useChartStore((s) => s.setTimeframe);

  return (
    <div className="flex gap-1">
      {TIMEFRAMES.map((tf) => (
        <button
          key={tf}
          onClick={() => setTimeframe(tf)}
          className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
            tf === timeframe
              ? "bg-zinc-100 text-zinc-900"
              : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          }`}
        >
          {tf.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
