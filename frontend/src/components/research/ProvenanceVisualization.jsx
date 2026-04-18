import React, { useEffect, useRef } from 'react';
import { Database, Target, CheckSquare, Zap } from 'lucide-react';

const ProvenanceVisualization = ({ provenance }) => {
  const containerRef = useRef(null);

  useEffect(() => {
    if (containerRef.current) {
      // SVG canvas for provenance tree visualization
      const container = containerRef.current;
      const width = container.offsetWidth;
      const height = 300;

      // Clear previous content
      container.innerHTML = '';

      // Create SVG
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('width', width);
      svg.setAttribute('height', height);
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`);

      // Draw tree structure: Data Sources → Thesis → Decisions → Gates

      const levels = [
        {
          label: 'Data Sources',
          items: provenance.data_sources || [],
          x: 60,
          icon: '📊',
        },
        {
          label: 'Trading Thesis',
          items: provenance.thesis_id ? [provenance.thesis_id] : [],
          x: width / 2,
          icon: '🎯',
        },
        {
          label: 'Decisions',
          items: provenance.decision_ids || [],
          x: width - 100,
          icon: '⚡',
        },
      ];

      let yOffset = 40;

      levels.forEach((level, levelIdx) => {
        if (level.items.length === 0) return;

        // Draw level label
        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        label.setAttribute('x', level.x);
        label.setAttribute('y', 20);
        label.setAttribute('text-anchor', 'middle');
        label.setAttribute('class', 'provenance-level-label');
        label.textContent = level.label;
        svg.appendChild(label);

        // Draw items
        const itemsPerRow = Math.ceil(Math.sqrt(level.items.length));
        let currentY = yOffset + 40;
        let currentX = level.x - (itemsPerRow * 50) / 2;

        level.items.slice(0, 3).forEach((item, itemIdx) => {
          // Draw box
          const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
          rect.setAttribute('x', currentX);
          rect.setAttribute('y', currentY);
          rect.setAttribute('width', 45);
          rect.setAttribute('height', 40);
          rect.setAttribute('rx', '4');
          rect.setAttribute('class', 'provenance-node');
          svg.appendChild(rect);

          // Draw text
          const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
          text.setAttribute('x', currentX + 22);
          text.setAttribute('y', currentY + 25);
          text.setAttribute('text-anchor', 'middle');
          text.setAttribute('font-size', '10');
          text.setAttribute('class', 'provenance-node-text');
          text.textContent = item.slice(0, 8);
          svg.appendChild(text);

          // Draw connection line to next level
          if (levelIdx < levels.length - 1) {
            const nextLevel = levels[levelIdx + 1];
            if (nextLevel.items.length > 0) {
              const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
              line.setAttribute('x1', currentX + 22);
              line.setAttribute('y1', currentY + 40);
              line.setAttribute('x2', level.x);
              line.setAttribute('y2', yOffset + 80);
              line.setAttribute('stroke', 'rgba(155, 127, 232, 0.3)');
              line.setAttribute('stroke-width', '1');
              line.setAttribute('stroke-dasharray', '4');
              svg.insertBefore(line, svg.firstChild);
            }
          }

          currentX += 55;
        });

        yOffset += 100;
      });

      // Draw gates at bottom
      if (provenance.policy_gates_applied && provenance.policy_gates_applied.length > 0) {
        const gatesY = yOffset;

        const gateLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        gateLabel.setAttribute('x', width / 2);
        gateLabel.setAttribute('y', gatesY - 10);
        gateLabel.setAttribute('text-anchor', 'middle');
        gateLabel.setAttribute('class', 'provenance-level-label');
        gateLabel.textContent = 'Compliance Gates';
        svg.appendChild(gateLabel);

        provenance.policy_gates_applied.slice(0, 3).forEach((gate, idx) => {
          const gateX = width / 2 - 75 + idx * 75;

          const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
          circle.setAttribute('cx', gateX);
          circle.setAttribute('cy', gatesY + 20);
          circle.setAttribute('r', '20');
          circle.setAttribute('class', 'provenance-gate');
          svg.appendChild(circle);

          const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
          text.setAttribute('x', gateX);
          text.setAttribute('y', gatesY + 25);
          text.setAttribute('text-anchor', 'middle');
          text.setAttribute('font-size', '24');
          text.textContent = '✓';
          svg.appendChild(text);
        });
      }

      container.appendChild(svg);
    }
  }, [provenance]);

  return (
    <div className="provenance-visualization">
      <svg ref={containerRef} style={{ width: '100%', minHeight: '300px' }} />
      <style>{`
        .provenance-level-label {
          font-size: 12px;
          font-weight: 600;
          fill: #dde1ea;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .provenance-node {
          fill: #181b21;
          stroke: #9b7fe8;
          stroke-width: 1.5;
          opacity: 0.8;
        }

        .provenance-node:hover {
          fill: #1e222a;
          stroke-width: 2;
          opacity: 1;
        }

        .provenance-node-text {
          fill: #4a9eff;
          font-weight: 500;
          font-family: 'JetBrains Mono', monospace;
        }

        .provenance-gate {
          fill: rgba(62, 207, 142, 0.15);
          stroke: #3ecf8e;
          stroke-width: 2;
        }
      `}</style>
    </div>
  );
};

export default ProvenanceVisualization;
