import React, { useEffect, useRef } from 'react';
import * as L from 'leaflet';
import { useMap } from 'react-leaflet';
import { FlowVectorsData } from '../types/terrain';

interface FlowVectorLayerProps {
  flowVectors: FlowVectorsData;
}

// D8 direction offsets → angle in degrees (for arrow rendering)
// 0: E, 1: SE, 2: S, 3: SW, 4: W, 5: NW, 6: N, 7: NE
const DIR_ANGLES: number[] = [0, 45, 90, 135, 180, 225, 270, 315];

function getArrowColor(slopeDeg: number): string {
  if (slopeDeg < 5) return '#38bdf8';   // flat - light blue
  if (slopeDeg < 15) return '#34d399';  // gentle - green
  if (slopeDeg < 30) return '#f59e0b';  // moderate - amber
  return '#f43f5e';                      // steep - red
}

export const FlowVectorLayer: React.FC<FlowVectorLayerProps> = ({ flowVectors }) => {
  const map = useMap();
  const layerGroupRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!flowVectors || !flowVectors.vectors || flowVectors.vectors.length === 0) return;

    // Clean up previous layer
    if (layerGroupRef.current) {
      map.removeLayer(layerGroupRef.current);
      layerGroupRef.current = null;
    }

    const group = L.layerGroup();

    for (const vec of flowVectors.vectors) {
      const angleDeg = DIR_ANGLES[vec.direction_idx] ?? 0;
      const color = getArrowColor(vec.slope_deg);

      // Render arrow as a small SVG DivIcon
      const svgArrow = `
        <svg width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg"
             style="transform: rotate(${angleDeg}deg); overflow: visible;">
          <line x1="8" y1="12" x2="8" y2="3" stroke="${color}" stroke-width="2" stroke-linecap="round"/>
          <polyline points="5,6 8,2 11,6" fill="none" stroke="${color}" stroke-width="1.8"
                    stroke-linejoin="round" stroke-linecap="round"/>
        </svg>
      `;

      const icon = L.divIcon({
        html: svgArrow,
        className: '',
        iconSize: [16, 16],
        iconAnchor: [8, 8],
      });

      L.marker([vec.lat, vec.lng], { icon, interactive: false }).addTo(group);
    }

    group.addTo(map);
    layerGroupRef.current = group;

    return () => {
      if (layerGroupRef.current) {
        map.removeLayer(layerGroupRef.current);
        layerGroupRef.current = null;
      }
    };
  }, [flowVectors, map]);

  return null;
};
