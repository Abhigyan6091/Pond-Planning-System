import React from 'react';
import { Polygon } from 'react-leaflet';
import { WatershedData } from '../types/terrain';

interface WatershedLayerProps {
  watershed: WatershedData;
}

export const WatershedLayer: React.FC<WatershedLayerProps> = ({ watershed }) => {
  if (!watershed || watershed.catchment_polygon.length < 3) return null;

  // coords are [lng, lat], Leaflet needs [lat, lng]
  const positions = watershed.catchment_polygon.map(
    (pt) => [pt[1], pt[0]] as [number, number]
  );

  return (
    <Polygon
      positions={positions}
      pathOptions={{
        color: '#6366f1',
        weight: 2.5,
        fillColor: '#4f46e5',
        fillOpacity: 0.3,
        dashArray: '8, 4',
      }}
    />
  );
};
