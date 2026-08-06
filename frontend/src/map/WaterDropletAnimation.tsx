import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { useMap } from 'react-leaflet';
import { LatLng, DropletPath } from '../types/terrain';

interface WaterDropletAnimationProps {
  dropletPath: DropletPath;
}

export const WaterDropletAnimation: React.FC<WaterDropletAnimationProps> = ({ dropletPath }) => {
  const map = useMap();
  const markerRef = useRef<L.Marker | null>(null);
  const polylineRef = useRef<L.Polyline | null>(null);
  const [animating, setAnimating] = useState(false);

  useEffect(() => {
    if (!dropletPath || dropletPath.path.length < 2) return;

    const path = dropletPath.path;

    // Draw the full flow path as a dashed blue trail
    const latlngs = path.map((p) => [p.lat, p.lng] as [number, number]);

    if (polylineRef.current) {
      map.removeLayer(polylineRef.current);
    }
    const polyline = L.polyline(latlngs, {
      color: '#06b6d4',
      weight: 2.5,
      opacity: 0.7,
      dashArray: '8, 5',
    }).addTo(map);
    polylineRef.current = polyline;

    // Create animated droplet marker
    const dropletIconHtml = `
      <div style="
        width: 14px; height: 14px;
        background: radial-gradient(circle at 35% 35%, #67e8f9, #0891b2);
        border-radius: 50% 50% 50% 0;
        transform: rotate(-45deg);
        box-shadow: 0 0 8px rgba(6,182,212,0.8);
        border: 1.5px solid rgba(255,255,255,0.5);
      "></div>
    `;
    const dropletIcon = L.divIcon({
      html: dropletIconHtml,
      className: '',
      iconSize: [14, 14],
      iconAnchor: [7, 7],
    });

    if (markerRef.current) {
      map.removeLayer(markerRef.current);
    }
    const marker = L.marker([path[0].lat, path[0].lng], { icon: dropletIcon }).addTo(map);
    markerRef.current = marker;

    // Animate the marker along the path
    let step = 0;
    setAnimating(true);

    const MAX_STEPS_PER_FRAME = 1;
    // Space out animation: ~40ms per step so the animation is visible
    const intervalMs = Math.max(20, Math.min(80, 3000 / path.length));

    const timer = setInterval(() => {
      if (step >= path.length) {
        clearInterval(timer);
        setAnimating(false);
        return;
      }
      const pt = path[step];
      marker.setLatLng([pt.lat, pt.lng]);
      step += MAX_STEPS_PER_FRAME;
    }, intervalMs);

    return () => {
      clearInterval(timer);
      if (markerRef.current) {
        map.removeLayer(markerRef.current);
        markerRef.current = null;
      }
      if (polylineRef.current) {
        map.removeLayer(polylineRef.current);
        polylineRef.current = null;
      }
    };
  }, [dropletPath, map]);

  return null;
};
