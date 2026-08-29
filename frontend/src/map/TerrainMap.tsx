import React, { useEffect } from 'react';
import {
  MapContainer, TileLayer, Marker, Rectangle, Polygon, Polyline,
  ImageOverlay, useMap, useMapEvents, Popup,
} from 'react-leaflet';
import * as L from 'leaflet';
import {
  LatLng, BoundingBox, ROISelectionMode, LayerVisibility,
  DemResponseData, ContourPolylineData, DropletPath, WatershedData,
  MapInteractionMode, SlopeResponseData, PondInfo,
  FlowVectorsData, StreamNetworkData, BasemapType, CandidateSite,
  ContourAnalysisResponse,
} from '../types/terrain';
import { ContourLayer } from './ContourLayer';
import { WaterDropletAnimation } from './WaterDropletAnimation';
import { WatershedLayer } from './WatershedLayer';
import { FlowVectorLayer } from './FlowVectorLayer';
import { StreamNetworkLayer } from './StreamNetworkLayer';

// ── Icons ──────────────────────────────────────────────────────────
const customIcon = new L.Icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34],
});

const createVertexIcon = (num: number) => new L.DivIcon({
  html: `<div style="width:20px;height:20px;background:#10b981;border-radius:50%;color:white;font-weight:bold;font-size:11px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 8px rgba(16,185,129,0.9);border:2px solid #ffffff">${num}</div>`,
  className: '', iconSize: [20, 20], iconAnchor: [10, 10],
});

const outletIcon = new L.DivIcon({
  html: `<div style="width:16px;height:16px;background:radial-gradient(circle,#818cf8,#4338ca);border-radius:50%;box-shadow:0 0 10px rgba(99,102,241,0.8);border:2px solid rgba(255,255,255,0.4)"></div>`,
  className: '', iconSize: [16, 16], iconAnchor: [8, 8],
});

const pondIcon = new L.DivIcon({
  html: `<div style="width:18px;height:18px;background:radial-gradient(circle,#3b82f6,#1d4ed8);border-radius:50%;box-shadow:0 0 12px rgba(59,130,246,0.9);border:2px solid #93c5fd"></div>`,
  className: '', iconSize: [18, 18], iconAnchor: [9, 9],
});

const profilePointIcon = new L.DivIcon({
  html: `<div style="width:14px;height:14px;background:#10b981;border-radius:50%;box-shadow:0 0 8px rgba(16,185,129,0.8);border:2px solid #ffffff"></div>`,
  className: '', iconSize: [14, 14], iconAnchor: [7, 7],
});

const TIER_COLORS: Record<string, string> = {
  'Recommended':      '#f59e0b',
  'Highly Suitable':  '#10b981',
  'Moderately Suitable': '#3b82f6',
  'Poor':             '#6b7280',
};

const createCandidateIcon = (tier: string, rank: number, isRecommended: boolean) => {
  const color = TIER_COLORS[tier] || '#6b7280';
  const size = isRecommended ? 28 : 22;
  const glow = isRecommended ? `box-shadow:0 0 16px ${color},0 0 4px #fff;` : `box-shadow:0 0 8px ${color}80;`;
  return new L.DivIcon({
    html: `<div style="width:${size}px;height:${size}px;background:${color};border-radius:50%;color:white;font-weight:bold;font-size:${isRecommended ? 13 : 11}px;display:flex;align-items:center;justify-content:center;${glow}border:2px solid white;z-index:${isRecommended ? 999 : 1}">${isRecommended ? '★' : rank}</div>`,
    className: '', iconSize: [size, size], iconAnchor: [size/2, size/2],
  });
};

// ── Basemap tile configs ───────────────────────────────────────────
const BASEMAPS = {
  osm: {
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; <a href="https://esri.com">Esri</a>, Maxar, Earthstar Geographics',
  },
  terrain: {
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://opentopomap.org">OpenTopoMap</a> | &copy; <a href="https://openstreetmap.org">OpenStreetMap</a>',
  },
};

// ── Event handlers ─────────────────────────────────────────────────
interface MapEventsHandlerProps {
  roiMode: ROISelectionMode;
  interactionMode: MapInteractionMode;
  demLoaded: boolean;
  onPointSelect: (pt: LatLng) => void;
  onPolygonPointAdd: (pt: LatLng) => void;
  onAnalysisClick: (pt: LatLng) => void;
}

const MapEventsHandler: React.FC<MapEventsHandlerProps> = ({
  roiMode, interactionMode, demLoaded, onPointSelect, onPolygonPointAdd, onAnalysisClick
}) => {
  useMapEvents({
    click(e) {
      const pt = { lat: e.latlng.lat, lng: e.latlng.lng };
      if (demLoaded && interactionMode !== 'select') {
        onAnalysisClick(pt);
      } else if (roiMode === 'polygon') {
        onPolygonPointAdd(pt);
      } else {
        onPointSelect(pt);
      }
    },
  });
  return null;
};

const MapRecenter: React.FC<{ center: LatLng | null }> = ({ center }) => {
  const map = useMap();
  useEffect(() => {
    if (center) map.flyTo([center.lat, center.lng], 13, { duration: 1.5 });
  }, [center, map]);
  return null;
};

// ── Props ─────────────────────────────────────────────────────────
interface TerrainMapProps {
  selectedPoint: LatLng | null;
  onPointSelect: (pt: LatLng) => void;
  computedBbox: BoundingBox | null;
  roiMode: ROISelectionMode;
  polygonPoints: LatLng[];
  onPolygonPointAdd: (pt: LatLng) => void;
  demData: DemResponseData | null;
  contours: ContourPolylineData[];
  selectedContour: ContourPolylineData | null;
  onSelectContour: (c: ContourPolylineData) => void;
  slopeData: SlopeResponseData | null;
  dropletPath: DropletPath | null;
  watershed: WatershedData | null;
  pond: PondInfo | null;
  profileTransect: LatLng[];
  interactionMode: MapInteractionMode;
  onAnalysisClick: (pt: LatLng) => void;
  watershedOutlet: LatLng | null;
  layers: LayerVisibility;
  flowVectors: FlowVectorsData | null;
  streamNetwork: StreamNetworkData | null;
  basemap: BasemapType;
  candidateSites: CandidateSite[];
  recommendedSite: CandidateSite | null;
  onCandidateClick?: (site: CandidateSite) => void;
  kmlResult?: ContourAnalysisResponse | null;
}

export const TerrainMap: React.FC<TerrainMapProps> = ({
  selectedPoint, onPointSelect, computedBbox, roiMode, polygonPoints,
  onPolygonPointAdd, demData, contours, selectedContour, onSelectContour,
  slopeData, dropletPath, watershed, pond, profileTransect,
  interactionMode, onAnalysisClick, watershedOutlet, layers,
  flowVectors, streamNetwork, basemap, candidateSites, recommendedSite,
  onCandidateClick, kmlResult,
}) => {
  const initialCenter: [number, number] = [20.5937, 78.9629]; // Centre of India

  const cursorClass = (interactionMode === 'droplet' || interactionMode === 'pond')
    ? 'cursor-crosshair'
    : (interactionMode === 'watershed' || interactionMode === 'profile' || roiMode === 'polygon')
    ? 'cursor-cell'
    : 'cursor-default';

  const bm = BASEMAPS[basemap] || BASEMAPS.osm;

  return (
    <div className={`w-full h-screen relative ${cursorClass}`}>
      <MapContainer center={initialCenter} zoom={5} zoomControl={false} className="w-full h-full">

        {/* Basemap tile layer */}
        <TileLayer key={basemap} attribution={bm.attribution} url={bm.url} maxZoom={19} />

        <MapEventsHandler
          roiMode={roiMode} interactionMode={interactionMode}
          demLoaded={!!demData} onPointSelect={onPointSelect}
          onPolygonPointAdd={onPolygonPointAdd} onAnalysisClick={onAnalysisClick}
        />
        <MapRecenter center={selectedPoint} />

        {/* Selected point marker */}
        {selectedPoint && (roiMode === 'point' || roiMode === 'rectangle') && interactionMode === 'select' && (
          <Marker position={[selectedPoint.lat, selectedPoint.lng]} icon={customIcon} />
        )}

        {/* Bounding box */}
        {computedBbox && (roiMode === 'point' || roiMode === 'rectangle') && (
          <Rectangle
            bounds={[[computedBbox.south, computedBbox.west], [computedBbox.north, computedBbox.east]]}
            pathOptions={{ color: '#3b82f6', weight: 2, fillColor: '#3b82f6', fillOpacity: 0.10, dashArray: '6,6' }}
          />
        )}

        {/* Polygon ROI */}
        {polygonPoints.length > 0 && (
          <>
            <Polygon
              positions={polygonPoints.map((p) => [p.lat, p.lng])}
              pathOptions={{ color: '#10b981', weight: 2.5, fillColor: '#10b981', fillOpacity: 0.18 }}
            />
            {polygonPoints.map((pt, idx) => (
              <Marker key={idx} position={[pt.lat, pt.lng]} icon={createVertexIcon(idx + 1)} />
            ))}
          </>
        )}

        {/* DEM Elevation Overlay */}
        {demData && layers.demOverlay && (
          <ImageOverlay
            url={demData.elevation_overlay_url}
            bounds={[[demData.metadata.bounds.south, demData.metadata.bounds.west], [demData.metadata.bounds.north, demData.metadata.bounds.east]]}
            opacity={basemap === 'satellite' ? 0.55 : 0.72}
          />
        )}

        {/* Hillshade */}
        {demData && layers.hillshade && (
          <ImageOverlay
            url={demData.hillshade_overlay_url}
            bounds={[[demData.metadata.bounds.south, demData.metadata.bounds.west], [demData.metadata.bounds.north, demData.metadata.bounds.east]]}
            opacity={0.75}
          />
        )}

        {/* Slope Heatmap */}
        {slopeData && layers.slopeHeatmap && demData && (
          <ImageOverlay
            url={slopeData.slope_heatmap_url}
            bounds={[[demData.metadata.bounds.south, demData.metadata.bounds.west], [demData.metadata.bounds.north, demData.metadata.bounds.east]]}
            opacity={0.68}
          />
        )}

        {/* Stream Network */}
        {streamNetwork && layers.streamNetwork && (
          <StreamNetworkLayer streamNetwork={streamNetwork} />
        )}

        {/* Contour Lines */}
        {layers.contours && demData && contours.length > 0 && (
          <ContourLayer
            contours={contours} selectedContour={selectedContour}
            onSelectContour={onSelectContour}
            minElev={demData.metadata.min_elevation}
            maxElev={demData.metadata.max_elevation}
          />
        )}

        {/* Flow Direction Vectors */}
        {flowVectors && layers.flowVectors && (
          <FlowVectorLayer flowVectors={flowVectors} />
        )}

        {/* Water Droplet Animation */}
        {dropletPath && dropletPath.path.length > 1 && (
          <WaterDropletAnimation dropletPath={dropletPath} />
        )}

        {/* Watershed Polygon */}
        {watershed && layers.watershed && (
          <WatershedLayer watershed={watershed} />
        )}

        {/* Watershed Outlet Marker */}
        {watershedOutlet && (
          <Marker position={[watershedOutlet.lat, watershedOutlet.lng]} icon={outletIcon} />
        )}

        {/* Pond Marker */}
        {pond && (
          <Marker position={[pond.center.lat, pond.center.lng]} icon={pondIcon} />
        )}

        {/* Transect Profile Line */}
        {profileTransect.length > 0 && (
          <>
            <Polyline
              positions={profileTransect.map((p) => [p.lat, p.lng])}
              pathOptions={{ color: '#10b981', weight: 3, dashArray: '6, 6' }}
            />
            {profileTransect.map((pt, idx) => (
              <Marker key={idx} position={[pt.lat, pt.lng]} icon={profilePointIcon} />
            ))}
          </>
        )}

        {/* Candidate Pond Sites */}
        {layers.candidateSites && candidateSites.map((site) => {
          const isRec = recommendedSite?.site_id === site.site_id;
          if (isRec && !layers.recommendedSite) return null;
          if (!isRec) return (
            <Marker
              key={site.site_id}
              position={[site.lat, site.lng]}
              icon={createCandidateIcon(site.suitability_tier, site.rank, false)}
              eventHandlers={{ click: () => onCandidateClick?.(site) }}
            >
              <Popup>
                <div style={{ fontFamily: 'monospace', fontSize: '12px', minWidth: '200px' }}>
                  <strong>#{site.rank} — {site.suitability_tier}</strong><br />
                  Score: <strong>{site.scores.composite_score.toFixed(1)}/100</strong><br />
                  Elevation: {site.elevation_m} m | Slope: {site.slope_deg}°<br />
                  Catchment: {site.catchment_area_km2.toFixed(3)} km²<br />
                  Est. Depth: {site.estimated_depth_m} m<br />
                  Est. Volume: {site.estimated_volume_m3.toLocaleString()} m³
                </div>
              </Popup>
            </Marker>
          );
          return null;
        })}

        {/* Recommended Site — separate so it's always on top */}
        {layers.recommendedSite && recommendedSite && (
          <Marker
            key={recommendedSite.site_id + '_rec'}
            position={[recommendedSite.lat, recommendedSite.lng]}
            icon={createCandidateIcon('Recommended', 1, true)}
            eventHandlers={{ click: () => onCandidateClick?.(recommendedSite) }}
          >
            <Popup>
              <div style={{ fontFamily: 'monospace', fontSize: '12px', minWidth: '220px' }}>
                <strong>⭐ RECOMMENDED SITE</strong><br />
                Score: <strong>{recommendedSite.scores.composite_score.toFixed(1)}/100</strong><br />
                Lat: {recommendedSite.lat.toFixed(5)}°, Lng: {recommendedSite.lng.toFixed(5)}°<br />
                Elevation: {recommendedSite.elevation_m} m | Slope: {recommendedSite.slope_deg}°<br />
                Catchment: {recommendedSite.catchment_area_km2.toFixed(3)} km²<br />
                Est. Depth: {recommendedSite.estimated_depth_m} m<br />
                Est. Volume: {recommendedSite.estimated_volume_m3.toLocaleString()} m³<br />
                {recommendedSite.estimated_runoff_m3 && <>Est. Runoff: {recommendedSite.estimated_runoff_m3.toLocaleString()} m³</>}
              </div>
            </Popup>
          </Marker>
        )}

        {/* ── Phase 2: KML Catchment Polygon ── */}
        {kmlResult?.catchment && kmlResult.catchment.boundary.length >= 3 && (
          <Polygon
            positions={kmlResult.catchment.boundary.map(
              (pt) => [pt[1], pt[0]] as [number, number]
            )}
            pathOptions={{
              color: '#06b6d4',
              weight: 3,
              fillColor: '#0891b2',
              fillOpacity: 0.35,
              dashArray: '6, 4',
            }}
          />
        )}

        {/* ── Phase 2: KML Recommended Pond Site Marker ── */}
        {kmlResult?.pond_site && (
          <Marker
            position={[kmlResult.pond_site.latitude, kmlResult.pond_site.longitude]}
            icon={createCandidateIcon('Recommended', 1, true)}
          >
            <Popup>
              <div style={{ fontFamily: 'monospace', fontSize: '12px', minWidth: '220px' }}>
                <strong>⭐ KML POND SITE</strong><br />
                Tier: <strong style={{ color: '#06b6d4' }}>{kmlResult.pond_site.suitability_tier}</strong><br />
                Score: <strong>{kmlResult.pond_site.suitability_score.toFixed(1)}/100</strong><br />
                Lat: {kmlResult.pond_site.latitude.toFixed(5)}°, Lng: {kmlResult.pond_site.longitude.toFixed(5)}°<br />
                Elevation: {kmlResult.pond_site.elevation_m} m | Slope: {kmlResult.pond_site.slope_deg}°<br />
                {kmlResult.catchment && <>Catchment: {kmlResult.catchment.area_km2.toFixed(3)} km²<br /></>}
                <p style={{ marginTop: '4px', fontSize: '11px', color: '#94a3b8' }}>{kmlResult.pond_site.reason}</p>
              </div>
            </Popup>
          </Marker>
        )}

      </MapContainer>

      {/* Mode tooltip overlays */}
      {roiMode === 'polygon' && interactionMode === 'select' && (
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-[900] bg-emerald-950/90 backdrop-blur-sm border border-emerald-500/50 text-emerald-200 text-xs px-4 py-2 rounded-full font-mono shadow-lg flex items-center space-x-2">
          <span>🛑 Click on map to add polygon vertices ({polygonPoints.length} points). Click 'Analyze Village' when ready.</span>
        </div>
      )}
      {interactionMode === 'droplet' && (
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-[900] bg-cyan-900/80 backdrop-blur-sm border border-cyan-500/50 text-cyan-200 text-xs px-4 py-2 rounded-full font-mono shadow-lg">
          💧 Click anywhere on the DEM to simulate a water droplet flowing downhill
        </div>
      )}
      {interactionMode === 'watershed' && (
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-[900] bg-indigo-900/80 backdrop-blur-sm border border-indigo-500/50 text-indigo-200 text-xs px-4 py-2 rounded-full font-mono shadow-lg">
          🌊 Click an outlet point to delineate its upstream watershed catchment
        </div>
      )}
      {interactionMode === 'pond' && (
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-[900] bg-blue-900/80 backdrop-blur-sm border border-blue-500/50 text-blue-200 text-xs px-4 py-2 rounded-full font-mono shadow-lg">
          🛢️ Click a terrain depression, valley, or lake to calculate pond depth and storage volume
        </div>
      )}
      {interactionMode === 'profile' && (
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-[900] bg-emerald-900/80 backdrop-blur-sm border border-emerald-500/50 text-emerald-200 text-xs px-4 py-2 rounded-full font-mono shadow-lg">
          📈 Click START point and END point on the map to sample the elevation profile
        </div>
      )}
    </div>
  );
};
