import React from 'react';
import { Polyline, Tooltip } from 'react-leaflet';
import { StreamNetworkData } from '../types/terrain';

interface StreamNetworkLayerProps {
  streamNetwork: StreamNetworkData;
}

// Stream order → color and weight (higher order = wider, more prominent)
const STREAM_STYLE: Record<number, { color: string; weight: number; opacity: number }> = {
  1: { color: '#93c5fd', weight: 1.0, opacity: 0.7 },   // tiny trickle - light blue
  2: { color: '#60a5fa', weight: 1.5, opacity: 0.75 },
  3: { color: '#3b82f6', weight: 2.0, opacity: 0.8 },
  4: { color: '#2563eb', weight: 2.5, opacity: 0.85 },
  5: { color: '#1d4ed8', weight: 3.5, opacity: 0.9 },   // major river - deep blue
};

export const StreamNetworkLayer: React.FC<StreamNetworkLayerProps> = ({ streamNetwork }) => {
  if (!streamNetwork || !streamNetwork.segments || streamNetwork.segments.length === 0) {
    return null;
  }

  return (
    <>
      {streamNetwork.segments.map((seg, idx) => {
        if (seg.coordinates.length < 2) return null;

        // Coords are [lng, lat] — Leaflet needs [lat, lng]
        const positions = seg.coordinates.map(
          ([lng, lat]) => [lat, lng] as [number, number]
        );

        const style = STREAM_STYLE[seg.stream_order] ?? STREAM_STYLE[5];

        return (
          <Polyline
            key={idx}
            positions={positions}
            pathOptions={{
              color: style.color,
              weight: style.weight,
              opacity: style.opacity,
              lineCap: 'round',
              lineJoin: 'round',
            }}
          >
            <Tooltip sticky>
              <div className="text-xs font-mono p-1">
                <div className="font-bold text-blue-400">Stream Network</div>
                <div>Strahler Order: <span className="text-slate-100 font-semibold">{seg.stream_order}</span></div>
              </div>
            </Tooltip>
          </Polyline>
        );
      })}
    </>
  );
};
