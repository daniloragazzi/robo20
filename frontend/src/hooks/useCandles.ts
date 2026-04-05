import { useQuery } from "@tanstack/react-query";
import { fetchCandles, type Candle } from "@/api/candles";

export function useCandles(symbol: string, timeframe: string, limit = 750) {
  return useQuery<Candle[]>({
    queryKey: ["candles", symbol, timeframe, limit],
    queryFn: () => fetchCandles(symbol, timeframe, limit),
  });
}
