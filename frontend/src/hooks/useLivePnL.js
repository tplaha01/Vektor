import { useState, useEffect, useMemo, useCallback } from 'react';
import { useRealTimeData } from './useRealTimeData';

export function useLivePnL(positions = []) {
  const { ticks, subscribeTicks } = useRealTimeData();
  const [livePnL, setLivePnL] = useState(0);
  const [livePnLBySymbol, setLivePnLBySymbol] = useState({});

  // Calculate PnL whenever positions or ticks change
  const calculatePnL = useCallback(() => {
    if (!positions || positions.length === 0) {
      setLivePnL(0);
      setLivePnLBySymbol({});
      return;
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

    setLivePnL(totalPnL);
    setLivePnLBySymbol(pnlBySymbol);
  }, [positions, ticks]);

  // Subscribe to tick updates
  useEffect(() => {
    const unsubscribe = subscribeTicks(() => {
      calculatePnL();
    });
    return unsubscribe;
  }, [subscribeTicks, calculatePnL]);

  // Initial calculation
  useEffect(() => {
    calculatePnL();
  }, [calculatePnL]);

  return {
    livePnL,
    livePnLBySymbol,
    isRealTime: Object.keys(ticks).length > 0,
  };
}
