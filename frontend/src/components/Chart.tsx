import { useEffect, useRef, useCallback, useState } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useCandles } from "@/hooks/useCandles";
import { useCandleStream, type CandleUpdate } from "@/hooks/useCandleStream";
import { useChartStore } from "@/stores/chartStore";
import { useIndicatorStore } from "@/stores/indicatorStore";
import { LiveIndicator } from "./LiveIndicator";
import { fetchCandles } from "@/api/candles";
import type { Candle } from "@/api/candles";
import type { IndicatorDataPoint, ChartIndicatorInstance } from "@/api/indicators";

function toBar(c: Candle | CandleUpdate) {
  return {
    time: (Math.floor(new Date(c.ts).getTime() / 1000)) as UTCTimestamp,
    open: Number(c.open),
    high: Number(c.high),
    low: Number(c.low),
    close: Number(c.close),
  };
}

function toTime(ts: string): UTCTimestamp {
  return Math.floor(new Date(ts).getTime() / 1000) as UTCTimestamp;
}

// Default colors for overlay line series
const OVERLAY_COLORS = [
  "#f59e0b", "#3b82f6", "#06b6d4", "#a855f7", "#ec4899",
  "#10b981", "#f43f5e", "#84cc16",
];

const INITIAL_LIMIT = 750;
const LOAD_MORE_BATCH = 500;
const MAX_CANDLES = 5000;

export function Chart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const seriesRef = useRef<any>(null);
  // Track indicator series to clean up
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const indicatorSeriesRef = useRef<Map<number, ISeriesApi<any>[]>>(new Map());

  const symbol = useChartStore((s) => s.symbol);
  const timeframe = useChartStore((s) => s.timeframe);
  const instances = useIndicatorStore((s) => s.instances);
  const data = useIndicatorStore((s) => s.data);
  const computeForInstance = useIndicatorStore((s) => s.computeForInstance);

  const { data: candles, isLoading } = useCandles(symbol, timeframe, INITIAL_LIMIT);

  // Accumulated candle history (initial + loaded-more)
  const allCandlesRef = useRef<Candle[]>([]);
  const [loadingMore, setLoadingMore] = useState(false);
  const noMoreDataRef = useRef(false);
  const isLoadingMoreRef = useRef(false);
  const initializedRef = useRef(false);

  // Create chart once
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      layout: {
        background: { color: "#09090b" },
        textColor: "#a1a1aa",
      },
      grid: {
        vertLines: { color: "#27272a" },
        horzLines: { color: "#27272a" },
      },
      crosshair: {
        mode: 0,
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: "#27272a",
      },
      rightPriceScale: {
        borderColor: "#27272a",
      },
    });

    const series = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderDownColor: "#ef4444",
      borderUpColor: "#22c55e",
      wickDownColor: "#ef4444",
      wickUpColor: "#22c55e",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      chart.applyOptions({ width, height });
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      indicatorSeriesRef.current.clear();
    };
  }, []);

  // Reset accumulation when symbol/timeframe changes
  useEffect(() => {
    initializedRef.current = false;
    allCandlesRef.current = [];
    noMoreDataRef.current = false;
  }, [symbol, timeframe]);

  // Set data when candles load (only once per symbol/timeframe)
  useEffect(() => {
    if (!seriesRef.current || !candles?.length) return;
    if (initializedRef.current) return; // skip background refetch resets
    initializedRef.current = true;
    allCandlesRef.current = candles;
    noMoreDataRef.current = false;
    const bars = candles.map(toBar);
    seriesRef.current.setData(bars);
    chartRef.current?.timeScale().fitContent();
    console.log("[Chart] initial load:", candles.length, "candles");
  }, [candles, symbol, timeframe]);

  // Load older candles when user scrolls to the left edge
  const loadOlderCandles = useCallback(async () => {
    if (isLoadingMoreRef.current || noMoreDataRef.current) return;
    if (allCandlesRef.current.length >= MAX_CANDLES) return;

    const oldest = allCandlesRef.current[0];
    if (!oldest) return;

    isLoadingMoreRef.current = true;
    setLoadingMore(true);
    try {
      console.log("[Chart] loading older candles before:", oldest.ts);
      const older = await fetchCandles(symbol, timeframe, LOAD_MORE_BATCH, oldest.ts);
      console.log("[Chart] received:", older.length, "older candles");
      if (!older.length) {
        noMoreDataRef.current = true;
        return;
      }
      // Prepend, deduplicate by ts
      const existingTimes = new Set(allCandlesRef.current.map((c) => c.ts));
      const fresh = older.filter((c) => !existingTimes.has(c.ts));
      if (!fresh.length) {
        noMoreDataRef.current = true;
        return;
      }
      const merged = [...fresh, ...allCandlesRef.current];
      // Trim to MAX_CANDLES from the end (keep newest)
      if (merged.length > MAX_CANDLES) {
        merged.splice(0, merged.length - MAX_CANDLES);
      }
      allCandlesRef.current = merged;

      if (!seriesRef.current || !chartRef.current) return;

      // Save current visible range to restore scroll position
      const timeScale = chartRef.current.timeScale();
      const visibleRange = timeScale.getVisibleLogicalRange();

      seriesRef.current.setData(merged.map(toBar));

      // Restore scroll position offset by number of prepended bars
      if (visibleRange) {
        const shift = fresh.length;
        timeScale.setVisibleLogicalRange({
          from: visibleRange.from + shift,
          to: visibleRange.to + shift,
        });
      }
    } catch (e) {
      console.error("[Chart] load older candles error:", e);
    } finally {
      isLoadingMoreRef.current = false;
      setLoadingMore(false);
    }
  }, [symbol, timeframe]);

  // Subscribe to visible range changes to detect scroll-to-left
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const handler = () => {
      const range = chart.timeScale().getVisibleLogicalRange();
      if (!range) return;
      const totalBars = allCandlesRef.current.length;
      const visibleSpan = range.to - range.from;
      // Skip when all/most data fits on screen (e.g. fitContent on initial load)
      if (totalBars > 0 && visibleSpan >= totalBars - 10) return;
      // Trigger load when user is within 10 bars of the left edge
      if (range.from < 10) {
        loadOlderCandles();
      }
    };

    chart.timeScale().subscribeVisibleLogicalRangeChange(handler);
    return () => {
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(handler);
    };
  }, [loadOlderCandles]);

  // Compute indicator data when instances, symbol, or timeframe change
  useEffect(() => {
    for (const inst of instances) {
      computeForInstance(inst, symbol, timeframe);
    }
  }, [instances, symbol, timeframe]);

  // Render indicator series on chart
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    // Remove old indicator series not in current instances
    const currentIds = new Set(instances.map((i) => i.id));
    for (const [id, seriesList] of indicatorSeriesRef.current) {
      if (!currentIds.has(id)) {
        for (const s of seriesList) {
          try { chart.removeSeries(s); } catch { /* already removed */ }
        }
        indicatorSeriesRef.current.delete(id);
      }
    }

    // Check if any marker-based indicators (mss/choch/lateralization) are still active
    const hasMarkerIndicator = instances.some(
      (i) => (i.indicator_type === "mss" || i.indicator_type === "choch" || i.indicator_type === "lateralization") && data[i.id]?.points.length,
    );
    // Clear markers if no marker indicators remain
    if (!hasMarkerIndicator && seriesRef.current) {
      try { seriesRef.current.setMarkers([]); } catch { /* ok */ }
    }

    // Add/update series for each instance
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const allMarkers: any[] = [];
    let colorIdx = 0;
    for (const inst of instances) {
      const instData = data[inst.id];
      if (!instData || instData.loading || !instData.points.length) continue;

      // Remove existing series for this instance (re-render)
      const existing = indicatorSeriesRef.current.get(inst.id);
      if (existing) {
        for (const s of existing) {
          try { chart.removeSeries(s); } catch { /* ok */ }
        }
      }

      try {
        const { series: newSeries, markers } = renderIndicatorSeries(
          chart,
          inst,
          instData.points,
          colorIdx,
          seriesRef.current,
        );
        indicatorSeriesRef.current.set(inst.id, newSeries);
        if (markers.length) allMarkers.push(...markers);
      } catch (e) {
        console.error("[Chart] indicator render error:", e);
      }
      colorIdx++;
    }

    // Set accumulated markers on candlestick series (merged from all indicators)
    if (seriesRef.current) {
      try {
        allMarkers.sort((a, b) => (a.time as number) - (b.time as number));
        seriesRef.current.setMarkers(allMarkers);
      } catch { /* ok */ }
    }
  }, [instances, data]);

  // WebSocket live updates
  const handleUpdate = useCallback((update: CandleUpdate) => {
    if (!seriesRef.current) return;
    seriesRef.current.update(toBar(update));
  }, []);

  const { connected } = useCandleStream(symbol, timeframe, handleUpdate);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />
      <LiveIndicator connected={connected} />
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-zinc-950/80">
          <span className="text-zinc-400">Carregando...</span>
        </div>
      )}
      {loadingMore && (
        <div className="absolute left-2 top-2 rounded bg-zinc-800/90 px-2 py-1 text-xs text-zinc-400">
          Carregando histórico...
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ //
//  Render indicator data as chart series                               //
// ------------------------------------------------------------------ //

function renderIndicatorSeries(
  chart: IChartApi,
  inst: ChartIndicatorInstance,
  points: IndicatorDataPoint[],
  colorIndex: number,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  _candleSeries: any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): { series: ISeriesApi<any>[]; markers: any[] } {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const series: ISeriesApi<any>[] = [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const markers: any[] = [];
  if (!points.length) return { series, markers };

  // Determine which value columns exist in the data
  const allKeys = new Set<string>();
  for (const pt of points) {
    for (const k of Object.keys(pt.values)) {
      allKeys.add(k);
    }
  }

  const color = (inst.params as Record<string, unknown>).color as string
    ?? OVERLAY_COLORS[colorIndex % OVERLAY_COLORS.length];

  const type = inst.indicator_type;

  // Overlay indicators — rendered as line series on the main price pane
  if (type === "ema" || type === "sma" || type === "vwap") {
    for (const key of allKeys) {
      const lineData = points
        .filter((p) => p.values[key] != null)
        .map((p) => ({ time: toTime(p.ts), value: p.values[key]! }));
      if (!lineData.length) continue;

      const s = chart.addLineSeries({
        color,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        title: inst.label || key,
      });
      s.setData(lineData);
      series.push(s);
    }
  }

  // Bollinger Bands — 3 lines (upper, middle, lower)
  else if (type === "bbands") {
    const upperKey = [...allKeys].find((k) => k.startsWith("BBU"));
    const midKey = [...allKeys].find((k) => k.startsWith("BBM"));
    const lowerKey = [...allKeys].find((k) => k.startsWith("BBL"));

    const bbColors = ["#3b82f6", "#6b7280", "#3b82f6"];
    const bbKeys = [upperKey, midKey, lowerKey];

    for (let i = 0; i < bbKeys.length; i++) {
      const key = bbKeys[i];
      if (!key) continue;
      const lineData = points
        .filter((p) => p.values[key] != null)
        .map((p) => ({ time: toTime(p.ts), value: p.values[key]! }));
      if (!lineData.length) continue;

      const s = chart.addLineSeries({
        color: bbColors[i],
        lineWidth: 1,
        lineStyle: i === 1 ? 0 : 2,
        priceLineVisible: false,
        lastValueVisible: false,
        title: i === 1 ? (inst.label || "BB") : "",
      });
      s.setData(lineData);
      series.push(s);
    }
  }

  // RSI — line series (oscillator pane via separate priceScale)
  else if (type === "rsi") {
    for (const key of allKeys) {
      const lineData = points
        .filter((p) => p.values[key] != null)
        .map((p) => ({ time: toTime(p.ts), value: p.values[key]! }));
      if (!lineData.length) continue;

      const s = chart.addLineSeries({
        color: "#a855f7",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: true,
        title: inst.label || "RSI",
        priceScaleId: "rsi",
      });
      s.setData(lineData);
      series.push(s);
    }
    // Configure the RSI price scale
    chart.priceScale("rsi").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
      borderColor: "#27272a",
    });
  }

  // MACD — line (macd + signal) in their own pane
  else if (type === "macd") {
    const macdKey = [...allKeys].find((k) => k.startsWith("MACD_") && !k.includes("h") && !k.includes("s"));
    const signalKey = [...allKeys].find((k) => k.startsWith("MACDs_"));
    const histKey = [...allKeys].find((k) => k.startsWith("MACDh_"));

    if (macdKey) {
      const lineData = points
        .filter((p) => p.values[macdKey] != null)
        .map((p) => ({ time: toTime(p.ts), value: p.values[macdKey]! }));
      if (lineData.length) {
        const s = chart.addLineSeries({
          color: "#3b82f6",
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          title: "MACD",
          priceScaleId: "macd",
        });
        s.setData(lineData);
        series.push(s);
      }
    }
    if (signalKey) {
      const lineData = points
        .filter((p) => p.values[signalKey] != null)
        .map((p) => ({ time: toTime(p.ts), value: p.values[signalKey]! }));
      if (lineData.length) {
        const s = chart.addLineSeries({
          color: "#f59e0b",
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          title: "Signal",
          priceScaleId: "macd",
        });
        s.setData(lineData);
        series.push(s);
      }
    }
    if (histKey) {
      const histData = points
        .filter((p) => p.values[histKey] != null)
        .map((p) => ({
          time: toTime(p.ts),
          value: p.values[histKey]!,
          color: Number(p.values[histKey]) >= 0 ? "#22c55e80" : "#ef444480",
        }));
      if (histData.length) {
        const s = chart.addHistogramSeries({
          priceLineVisible: false,
          lastValueVisible: false,
          priceScaleId: "macd",
        });
        s.setData(histData);
        series.push(s);
      }
    }
    chart.priceScale("macd").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
      borderColor: "#27272a",
    });
  }

  // Stochastic — two lines (%K and %D) in pane
  else if (type === "stoch") {
    const kKey = [...allKeys].find((k) => k.startsWith("STOCHk"));
    const dKey = [...allKeys].find((k) => k.startsWith("STOCHd"));

    for (const [key, c] of [[kKey, "#3b82f6"], [dKey, "#f59e0b"]] as const) {
      if (!key) continue;
      const lineData = points
        .filter((p) => p.values[key] != null)
        .map((p) => ({ time: toTime(p.ts), value: p.values[key]! }));
      if (!lineData.length) continue;
      const s = chart.addLineSeries({
        color: c,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        title: key,
        priceScaleId: "stoch",
      });
      s.setData(lineData);
      series.push(s);
    }
    chart.priceScale("stoch").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
      borderColor: "#27272a",
    });
  }

  // ATR — line in its own pane
  else if (type === "atr") {
    for (const key of allKeys) {
      const lineData = points
        .filter((p) => p.values[key] != null)
        .map((p) => ({ time: toTime(p.ts), value: p.values[key]! }));
      if (!lineData.length) continue;
      const s = chart.addLineSeries({
        color: "#06b6d4",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: true,
        title: inst.label || "ATR",
        priceScaleId: "atr",
      });
      s.setData(lineData);
      series.push(s);
    }
    chart.priceScale("atr").applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
      borderColor: "#27272a",
    });
  }

  // Volume — histogram in its own pane
  else if (type === "volume") {
    const volSmaKey = [...allKeys].find((k) => k === "vol_sma");
    if (volSmaKey) {
      const lineData = points
        .filter((p) => p.values[volSmaKey] != null)
        .map((p) => ({ time: toTime(p.ts), value: p.values[volSmaKey]! }));
      if (lineData.length) {
        const s = chart.addLineSeries({
          color: "#6b7280",
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          title: "Vol SMA",
          priceScaleId: "vol",
        });
        s.setData(lineData);
        series.push(s);
      }
    }
    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
      borderColor: "#27272a",
    });
  }

  // Price action (MSS, CHoCH) — dashed horizontal lines from broken swing to breakout
  else if (type === "mss" || type === "choch") {
    const signalKey = type === "mss" ? "mss_signal" : "choch_signal";
    const label = type.toUpperCase();

    // ── Zigzag line connecting swing highs and lows ──
    {
      const zigzagData: { time: UTCTimestamp; value: number }[] = [];
      for (const p of points) {
        const sh = p.values.swing_high;
        const sl = p.values.swing_low;
        if (sh != null && !isNaN(Number(sh))) {
          zigzagData.push({ time: toTime(p.ts), value: Number(sh) });
        }
        if (sl != null && !isNaN(Number(sl))) {
          zigzagData.push({ time: toTime(p.ts), value: Number(sl) });
        }
      }
      if (zigzagData.length > 1) {
        // Sort by time, deduplicate (keep last if same time)
        zigzagData.sort((a, b) => (a.time as number) - (b.time as number));
        const deduped: typeof zigzagData = [];
        for (const d of zigzagData) {
          if (deduped.length && deduped[deduped.length - 1].time === d.time) {
            deduped[deduped.length - 1] = d; // overwrite with last
          } else {
            deduped.push(d);
          }
        }
        if (deduped.length > 1) {
          const zigzag = chart.addLineSeries({
            color: "#888888",
            lineWidth: 1,
            lineStyle: 0, // Solid
            crosshairMarkerVisible: false,
            priceLineVisible: false,
            lastValueVisible: false,
            title: "",
            pointMarkersVisible: true,
            pointMarkersRadius: 3,
          });
          zigzag.setData(deduped);
          series.push(zigzag);
        }
      }
    }

    // Collect signal points that have break info
    const signals = points.filter(
      (p) =>
        p.values[signalKey] != null &&
        p.values[signalKey] !== 0 &&
        p.values.break_level != null &&
        p.values.break_start_ts != null,
    );

    // Draw a dashed horizontal line for each signal (from swing to breakout)
    for (const pt of signals) {
      const isBull = (pt.values[signalKey] as number) > 0;
      const breakLevel = pt.values.break_level as number;
      let startTs = pt.values.break_start_ts as string;
      // Ensure UTC parsing (backend may omit Z suffix)
      if (!startTs.endsWith("Z") && !startTs.includes("+")) {
        startTs = startTs.split(".")[0] + "Z";
      }
      const lineColor = isBull ? "#22c55e" : "#ef4444";

      const t0 = toTime(startTs);
      const t1 = toTime(pt.ts);
      // Skip if times are equal or out of order
      if (t0 >= t1) continue;

      // Midpoint time for label placement
      const tMid = Math.round((t0 + t1) / 2) as UTCTimestamp;

      const s = chart.addLineSeries({
        color: lineColor,
        lineWidth: 1,
        lineStyle: 2, // Dashed
        crosshairMarkerVisible: false,
        priceLineVisible: false,
        lastValueVisible: false,
        title: "",
      });
      s.setData([
        { time: t0, value: breakLevel },
        { time: tMid, value: breakLevel },
        { time: t1, value: breakLevel },
      ]);
      // Place label at the midpoint of the dashed line
      s.setMarkers([{
        time: tMid,
        position: isBull ? "aboveBar" : "belowBar",
        color: lineColor,
        shape: "square",
        size: 0,
        text: label,
      }]);
      series.push(s);
    }
  }

  // Lateralization — range bands + breakout signals
  else if (type === "lateralization") {
    // ── Zigzag line connecting swing highs and lows ──
    {
      const zigzagData: { time: UTCTimestamp; value: number }[] = [];
      for (const p of points) {
        const sh = p.values.swing_high;
        const sl = p.values.swing_low;
        if (sh != null && !isNaN(Number(sh))) {
          zigzagData.push({ time: toTime(p.ts), value: Number(sh) });
        }
        if (sl != null && !isNaN(Number(sl))) {
          zigzagData.push({ time: toTime(p.ts), value: Number(sl) });
        }
      }
      if (zigzagData.length > 1) {
        zigzagData.sort((a, b) => (a.time as number) - (b.time as number));
        const deduped: typeof zigzagData = [];
        for (const d of zigzagData) {
          if (deduped.length && deduped[deduped.length - 1].time === d.time) {
            deduped[deduped.length - 1] = d;
          } else {
            deduped.push(d);
          }
        }
        if (deduped.length > 1) {
          const zigzag = chart.addLineSeries({
            color: "#888888",
            lineWidth: 1,
            lineStyle: 0,
            crosshairMarkerVisible: false,
            priceLineVisible: false,
            lastValueVisible: false,
            title: "",
            pointMarkersVisible: true,
            pointMarkersRadius: 3,
          });
          zigzag.setData(deduped);
          series.push(zigzag);
        }
      }
    }

    // ── Range bands (top + bottom) ──
    const topData: { time: UTCTimestamp; value: number }[] = [];
    const bottomData: { time: UTCTimestamp; value: number }[] = [];
    for (const p of points) {
      const rt = p.values.range_top;
      const rb = p.values.range_bottom;
      if (rt != null && rb != null) {
        const t = toTime(p.ts);
        topData.push({ time: t, value: Number(rt) });
        bottomData.push({ time: t, value: Number(rb) });
      }
    }
    if (topData.length > 1) {
      const topLine = chart.addLineSeries({
        color: "#f59e0b",
        lineWidth: 1,
        lineStyle: 2,
        crosshairMarkerVisible: false,
        priceLineVisible: false,
        lastValueVisible: false,
        title: "",
      });
      topLine.setData(topData);
      series.push(topLine);

      const bottomLine = chart.addLineSeries({
        color: "#f59e0b",
        lineWidth: 1,
        lineStyle: 2,
        crosshairMarkerVisible: false,
        priceLineVisible: false,
        lastValueVisible: false,
        title: "",
      });
      bottomLine.setData(bottomData);
      series.push(bottomLine);
    }

    // ── Breakout signals ──
    const breakouts = points.filter(
      (p) => p.values.range_signal != null && p.values.range_signal !== 0,
    );
    for (const pt of breakouts) {
      const isBull = (pt.values.range_signal as number) > 0;
      markers.push({
        time: toTime(pt.ts),
        position: isBull ? "belowBar" : "aboveBar",
        color: isBull ? "#22c55e" : "#ef4444",
        shape: isBull ? "arrowUp" : "arrowDown",
        text: isBull ? "BREAKOUT ↑" : "BREAKOUT ↓",
      });
    }
  }

  // FVG — Fair Value Gaps rendered as shaded zones (top + bottom lines per gap)
  else if (type === "fvg") {
    const gaps = points.filter((p) => p.values.fvg_direction != null);
    if (!gaps.length) return { series, markers };

    // Collect all top/bottom levels into two continuous series for rendering
    const bullishTops: { time: UTCTimestamp; value: number }[] = [];
    const bullishBottoms: { time: UTCTimestamp; value: number }[] = [];
    const bearishTops: { time: UTCTimestamp; value: number }[] = [];
    const bearishBottoms: { time: UTCTimestamp; value: number }[] = [];

    for (const pt of gaps) {
      const top = pt.values.fvg_top;
      const bottom = pt.values.fvg_bottom;
      if (top == null || bottom == null) continue;
      const t = toTime(pt.ts);
      const isBullish = Number(pt.values.fvg_direction) > 0;
      if (isBullish) {
        bullishTops.push({ time: t, value: Number(top) });
        bullishBottoms.push({ time: t, value: Number(bottom) });
      } else {
        bearishTops.push({ time: t, value: Number(top) });
        bearishBottoms.push({ time: t, value: Number(bottom) });
      }
    }

    // Render bullish FVG lines
    if (bullishTops.length) {
      const s1 = chart.addLineSeries({
        color: "#22c55e60",
        lineWidth: 1,
        lineStyle: 2,
        crosshairMarkerVisible: false,
        pointMarkersVisible: true,
        pointMarkersRadius: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        title: "FVG Bull ↑",
      });
      s1.setData(bullishTops);
      series.push(s1);

      const s2 = chart.addLineSeries({
        color: "#22c55e60",
        lineWidth: 1,
        lineStyle: 2,
        crosshairMarkerVisible: false,
        pointMarkersVisible: true,
        pointMarkersRadius: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        title: "",
      });
      s2.setData(bullishBottoms);
      series.push(s2);
    }

    // Render bearish FVG lines
    if (bearishTops.length) {
      const s1 = chart.addLineSeries({
        color: "#ef444460",
        lineWidth: 1,
        lineStyle: 2,
        crosshairMarkerVisible: false,
        pointMarkersVisible: true,
        pointMarkersRadius: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        title: "FVG Bear ↓",
      });
      s1.setData(bearishTops);
      series.push(s1);

      const s2 = chart.addLineSeries({
        color: "#ef444460",
        lineWidth: 1,
        lineStyle: 2,
        crosshairMarkerVisible: false,
        pointMarkersVisible: true,
        pointMarkersRadius: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        title: "",
      });
      s2.setData(bearishBottoms);
      series.push(s2);
    }
  }

  // Fibonacci — line series for each fib level
  else if (type === "fibonacci") {
    const fibKeys = [...allKeys].filter((k) => k.startsWith("fib_") && k !== "fib_direction" && k !== "fib_signal");
    const fibColors = ["#fbbf24", "#fb923c", "#f87171", "#a78bfa", "#818cf8"];
    let fi = 0;
    for (const key of fibKeys) {
      const lineData = points
        .filter((p) => p.values[key] != null)
        .map((p) => ({ time: toTime(p.ts), value: p.values[key]! }));
      if (!lineData.length) continue;
      const s = chart.addLineSeries({
        color: fibColors[fi % fibColors.length],
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        title: key.replace("fib_", ""),
      });
      s.setData(lineData);
      series.push(s);
      fi++;
    }
  }

  // Fallback: render all keys as overlay lines
  else {
    for (const key of allKeys) {
      const lineData = points
        .filter((p) => p.values[key] != null)
        .map((p) => ({ time: toTime(p.ts), value: p.values[key]! }));
      if (!lineData.length) continue;
      const s = chart.addLineSeries({
        color: OVERLAY_COLORS[colorIndex % OVERLAY_COLORS.length],
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        title: key,
      });
      s.setData(lineData);
      series.push(s);
    }
  }

  return { series, markers };
}
