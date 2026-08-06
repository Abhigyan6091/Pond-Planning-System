import React from 'react';
import { Polyline, Tooltip } from 'react-leaflet';
import * as L from 'leaflet';
import { ContourPolylineData } from '../types/terrain';

interface ContourLayerProps {
  contours: ContourPolylineData[];
  selectedContour: ContourPolylineData | null;
  onSelectContour: (contour: ContourPolylineData) => void;
  minElev: number;
  maxElev: number;
}

export const ContourLayer: React.FC<ContourLayerProps> = ({
  contours,
  selectedContour,
  onSelectContour,
  minElev,
  maxElev,
}) => {
  const getContourColor = (elev: number, isSelected: boolean) => {
    if (isSelected) return '#06b6d4';
    const ratio = Math.max(0, Math.min(1, (elev - minElev) / (maxElev - minElev + 1e-6)));
    if (ratio < 0.25) return '#34d399';
    if (ratio < 0.6) return '#f59e0b';
    return '#f43f5e';
  };

  return (
    <>
      {contours.map((contour) => {
        const isSelected = selectedContour?.id === contour.id;
        const positions = contour.coordinates.map((pt) => [pt[1], pt[0]] as [number, number]);
        const color = getContourColor(contour.elevation, isSelected);

        return (
          <Polyline
            key={contour.id}
            positions={positions}
            pathOptions={{
              color: color,
              weight: isSelected ? 4 : 1.5,
              opacity: isSelected ? 1.0 : 0.8,
            }}
            eventHandlers={{
              click: (e) => {
                L.DomEvent.stopPropagation(e);
                onSelectContour(contour);
              },
            }}
          >
            <Tooltip sticky>
              <div className="text-xs space-y-1 font-mono p-1">
                <div className="font-bold text-cyan-400">Contour Isolines</div>
                <div>Elevation: <span className="font-semibold text-slate-100">{contour.elevation} m</span></div>
                <div>Arc Length: <span className="font-semibold text-slate-100">{contour.length_km} km ({contour.length_m} m)</span></div>
                <div>Vertices: <span className="font-semibold text-slate-100">{contour.vertex_count}</span></div>
                {contour.is_closed && contour.area_km2 !== null && (
                  <div className="text-emerald-400 font-semibold">
                    Enclosed Area: {contour.area_km2} km² ({contour.area_m2} m²)
                  </div>
                )}
              </div>
            </Tooltip>
          </Polyline>
        );
      })}
    </>
  );
};
