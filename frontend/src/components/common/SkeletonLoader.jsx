import React from 'react';
import '../../styles/skeleton.css';

export default function SkeletonLoader({ type = 'card', count = 1 }) {
  if (type === 'card') {
    return (
      <>
        {Array(count).fill(0).map((_, i) => (
          <div key={i} className="skeleton-card">
            <div className="skeleton-line skeleton-line-title"></div>
            <div className="skeleton-line skeleton-line-text"></div>
            <div className="skeleton-line skeleton-line-text short"></div>
          </div>
        ))}
      </>
    );
  }
  
  if (type === 'kpi') {
    return (
      <div className="skeleton-kpi">
        <div className="skeleton-line skeleton-line-label"></div>
        <div className="skeleton-line skeleton-line-value"></div>
        <div className="skeleton-line skeleton-line-meta"></div>
      </div>
    );
  }
  
  if (type === 'row') {
    return (
      <div className="skeleton-row">
        <div className="skeleton-line skeleton-line-row"></div>
        <div className="skeleton-line skeleton-line-row"></div>
        <div className="skeleton-line skeleton-line-row short"></div>
      </div>
    );
  }
  
  return null;
}
