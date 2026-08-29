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
    if (isSelected) return '#00f0ff';
    const ratio = Math.max(0, Math.min(1, (elev - minElev) / (maxElev - minElev + 1e-6)));
    if (ratio < 0.20) return '#10b981'; // Emerald for valley lowlands
    if (ratio < 0.45) return '#06b6d4'; // Cyan for lower slopes
    if (ratio < 0.70) return '#f59e0b'; // Amber for mid terrain
    return '#f43f5e';                  // Coral/Rose for ridge tops
  };

  return (
    <>
      {contours.map((contour) => {
        const isSelected = selectedContour?.id === contour.id;
        const isIndexContour = contour.elevation % 5 === 0 || contour.elevation % 10 === 0;
        const positions = contour.coordinates.map((pt) => [pt[1], pt[0]] as [number, number]);
        const color = getContourColor(contour.elevation, isSelected);

        return (
          <Polyline
            key={contour.id}
            positions={positions}
            pathOptions={{
              color: color,
              weight: isSelected ? 4.5 : isIndexContour ? 2.6 : 1.8,
              opacity: isSelected ? 1.0 : isIndexContour ? 0.95 : 0.85,
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
                <div className="font-bold text-cyan-400">Contour Isoline</div>
                <div>Elevation: <span className="font-semibold text-white px-1 py-0.5 rounded bg-slate-800">{contour.elevation} m</span></div>
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
