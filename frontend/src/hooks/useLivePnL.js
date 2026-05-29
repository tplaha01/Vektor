import { useMemo } from 'react';
import { useRealTimeData } from './useRealTimeData';

export function useLivePnL(positions = []) {
  const { ticks } = useRealTimeData();

  const { livePnL, livePnLBySymbol } = useMemo(() => {
    if (!positions || positions.length === 0) {
      return { livePnL: 0, livePnLBySymbol: {} };
    }

    let totalPnL = 0;
    const pnlBySymbol = {};

    positions.forEach(pos => {
      const symbol = pos.symbol;
      const qty = pos.qty || 0;
      const avgPrice = pos.avg_price || 0;
      const currentTick = ticks[symbol];
      const currentPrice = currentTick?.price || avgPrice;

      if (qty && avgPrice && currentPrice) {
        const pnl = (currentPrice - avgPrice) * qty;
        pnlBySymbol[symbol] = {
          qty,
          avgPrice,
          currentPrice,
          pnl,
          pnlPct: ((currentPrice - avgPrice) / avgPrice * 100),
        };
        totalPnL += pnl;
      }
    });

    return { livePnL: totalPnL, livePnLBySymbol: pnlBySymbol };
  }, [positions, ticks]);

  return {
    livePnL,
    livePnLBySymbol,
    isRealTime: Object.keys(ticks).length > 0,
  };
}
