import React from 'react';
import '../../styles/spark-chart.css';

export default function SparkChart({ values = [], color = '#3ecf8e', height = 30 }) {
  if (!values || values.length === 0) return <div className="spark-chart-empty">—</div>;
  
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const normalized = values.map(v => (v - min) / range);
  
  const points = normalized.map((v, i) => {
    const x = (i / (values.length - 1 || 1)) * 100;
    const y = (1 - v) * height;
    return `${x},${y}`;
  }).join(' ');
  
  const trend = values.length > 1 
    ? values[values.length - 1] > values[0] 
      ? 'up' 
      : 'down'
    : 'flat';
  
  return (
    <div className="spark-chart">
      <svg width="100%" height={height} viewBox={`0 0 100 ${height}`} preserveAspectRatio="none">
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
          className={`spark-line spark-${trend}`}
        />
        <polyline
          points={points}
          fill={`url(#sparkGradient-${trend})`}
          stroke="none"
          opacity="0.1"
          vectorEffect="non-scaling-stroke"
        />
        <defs>
          <linearGradient id={`sparkGradient-${trend}`} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
}
