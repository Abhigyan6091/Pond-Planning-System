import React, { useState, useMemo, useEffect } from 'react';
import {
  LatLng, BoundingBox, ROISelectionMode, DemProvider, LayerVisibility,
  DemResponseData, ContourPolylineData, SlopeResponseData, DropletPath,
  WatershedData, MapInteractionMode, PondInfo, ElevationProfileResponseData, Terrain3DData
} from '../types/terrain';
import { TopToolbar } from '../components/TopToolbar';
import { LeftSidebar } from '../components/LeftSidebar';
import { StatsPanel } from '../components/StatsPanel';
import { ContourInspector } from '../components/ContourInspector';
import { HydrologyInspector } from '../components/HydrologyInspector';
import { PondInspector } from '../components/PondInspector';
import { ElevationProfileModal } from '../components/ElevationProfileModal';
import { Terrain3DModal } from '../components/Terrain3DModal';
import { TerrainMap } from '../map/TerrainMap';
import { demService } from '../services/api';
import { Download, Trash2, Hexagon } from 'lucide-react';

export const Dashboard: React.FC = () => {
  // --- ROI / DEM state ---
  const [selectedPoint, setSelectedPoint] = useState<LatLng | null>({ lat: 27.9881, lng: 86.9250 });
  const [radiusKm, setRadiusKm] = useState<number>(2.0);
  const [roiMode, setRoiMode] = useState<ROISelectionMode>('point');
  const [polygonPoints, setPolygonPoints] = useState<LatLng[]>([]);
  const [provider, setProvider] = useState<DemProvider>('openzenith');
  const [isLoading, setIsLoading] = useState(false);
  const [demData, setDemData] = useState<DemResponseData | null>(null);

  // --- Phase 2: Contours ---
  const [contourInterval, setContourInterval] = useState<number>(20.0);
  const [contours, setContours] = useState<ContourPolylineData[]>([]);
  const [selectedContour, setSelectedContour] = useState<ContourPolylineData | null>(null);

  // --- Phase 3: Slope / Hydrology ---
  const [slopeData, setSlopeData] = useState<SlopeResponseData | null>(null);
  const [interactionMode, setInteractionMode] = useState<MapInteractionMode>('select');
  const [dropletPath, setDropletPath] = useState<DropletPath | null>(null);
  const [watershed, setWatershed] = useState<WatershedData | null>(null);
  const [watershedOutlet, setWatershedOutlet] = useState<LatLng | null>(null);

  // --- Phase 4: Ponds, Profile, 3D ---
  const [pond, setPond] = useState<PondInfo | null>(null);
  const [profileTransect, setProfileTransect] = useState<LatLng[]>([]);
  const [profileData, setProfileData] = useState<ElevationProfileResponseData | null>(null);
  const [data3D, setData3D] = useState<Terrain3DData | null>(null);
  const [is3DOpen, setIs3DOpen] = useState(false);

  const [analysisLoading, setAnalysisLoading] = useState(false);

  const [layers, setLayers] = useState<LayerVisibility>({
    contours: true,
    demOverlay: true,
    hillshade: true,
    watershed: true,
    slopeHeatmap: false,
  });

  const computedBbox: BoundingBox | null = useMemo(() => {
    if (!selectedPoint) return null;
    const latDelta = radiusKm / 111.0;
    const lngDelta = radiusKm / (111.0 * Math.cos((selectedPoint.lat * Math.PI) / 180.0));
    return {
      south: selectedPoint.lat - latDelta,
      north: selectedPoint.lat + latDelta,
      west: selectedPoint.lng - lngDelta,
      east: selectedPoint.lng + lngDelta,
    };
  }, [selectedPoint, radiusKm]);

  const handleToggleLayer = (key: keyof LayerVisibility) =>
    setLayers((prev) => ({ ...prev, [key]: !prev[key] }));

  const handleRoiModeChange = (mode: ROISelectionMode) => {
    setRoiMode(mode);
    if (mode === 'polygon') setPolygonPoints([]);
  };

  // Regenerate contours whenever interval or DEM changes
  useEffect(() => {
    if (!demData) return;
    demService.generateContours(
      demData.metadata.dem_id,
      demData.elevation_matrix,
      demData.metadata.bounds,
      contourInterval
    ).then((res) => {
      setContours(res.contours);
      setSelectedContour(null);
    }).catch(console.error);
  }, [contourInterval, demData]);

  const resetAnalysisState = () => {
    setDropletPath(null);
    setWatershed(null);
    setWatershedOutlet(null);
    setPond(null);
    setProfileTransect([]);
    setProfileData(null);
  };

  const handleDownloadDem = async () => {
    setIsLoading(true);
    setSelectedContour(null);
    resetAnalysisState();
    setSlopeData(null);

    try {
      const payload: any = { provider, dem_type: 'COP30', resolution: 100 };
      if (roiMode === 'polygon' && polygonPoints.length >= 3) {
        payload.polygon = { coordinates: polygonPoints.map((p) => [p.lng, p.lat]) };
      } else if (selectedPoint) {
        payload.center = selectedPoint;
        payload.radius_km = radiusKm;
      }

      const res = await demService.downloadDem(payload);
      setDemData(res);

      // Auto-generate contours
      const cRes = await demService.generateContours(
        res.metadata.dem_id, res.elevation_matrix, res.metadata.bounds, contourInterval
      );
      setContours(cRes.contours);

      // Auto-compute slope heatmap
      const sRes = await demService.computeSlope(
        res.metadata.dem_id, res.elevation_matrix, res.metadata.bounds, res.metadata.pixel_size_m
      );
      setSlopeData(sRes);
    } catch (err) {
      console.error(err);
      alert('Error fetching DEM. Check backend is running on port 8000.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAnalysisClick = async (pt: LatLng) => {
    if (!demData || analysisLoading) return;

    if (interactionMode === 'droplet') {
      setAnalysisLoading(true);
      try {
        setDropletPath(null);
        const res = await demService.simulateDroplet(
          pt, demData.elevation_matrix, demData.metadata.bounds, demData.metadata.pixel_size_m
        );
        setDropletPath(res);
      } catch (err) {
        console.error(err);
      } finally {
        setAnalysisLoading(false);
      }
    } else if (interactionMode === 'watershed') {
      setAnalysisLoading(true);
      try {
        setWatershed(null);
        setWatershedOutlet(pt);
        const res = await demService.delineateWatershed(
          pt, demData.elevation_matrix, demData.metadata.bounds, demData.metadata.pixel_size_m
        );
        setWatershed(res);
      } catch (err) {
        console.error(err);
      } finally {
        setAnalysisLoading(false);
      }
    } else if (interactionMode === 'pond') {
      setAnalysisLoading(true);
      try {
        setPond(null);
        const res = await demService.detectPond(
          pt, demData.elevation_matrix, demData.metadata.bounds, demData.metadata.pixel_size_m
        );
        if (res.success && res.pond) {
          setPond(res.pond);
        } else {
          alert(res.message || 'No depression found at click location.');
        }
      } catch (err) {
        console.error(err);
      } finally {
        setAnalysisLoading(false);
      }
    } else if (interactionMode === 'profile') {
      if (profileTransect.length === 0 || profileTransect.length >= 2) {
        setProfileTransect([pt]);
        setProfileData(null);
      } else if (profileTransect.length === 1) {
        const startPt = profileTransect[0];
        const endPt = pt;
        setProfileTransect([startPt, endPt]);
        setAnalysisLoading(true);
        try {
          const res = await demService.computeElevationProfile(
            startPt, endPt, demData.elevation_matrix, demData.metadata.bounds, demData.metadata.pixel_size_m
          );
          setProfileData(res);
        } catch (err) {
          console.error(err);
        } finally {
          setAnalysisLoading(false);
        }
      }
    }
  };

  const handleOpen3DTerrain = async () => {
    if (!demData) return;
    if (data3D && data3D.dem_id === demData.metadata.dem_id) {
      setIs3DOpen(true);
      return;
    }
    setAnalysisLoading(true);
    try {
      const res = await demService.fetchTerrain3D(
        demData.elevation_matrix, demData.metadata.bounds, demData.metadata.dem_id, 2
      );
      setData3D(res);
      setIs3DOpen(true);
    } catch (err) {
      console.error('3D terrain error:', err);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const showHydroInspector = !!(dropletPath || watershed);

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-[#0a0d14]">
      <TopToolbar
        selectedPoint={selectedPoint}
        radiusKm={radiusKm}
        onRadiusChange={setRadiusKm}
        roiMode={roiMode}
        onRoiModeChange={handleRoiModeChange}
        provider={provider}
        onProviderChange={setProvider}
        contourInterval={contourInterval}
        onContourIntervalChange={setContourInterval}
        interactionMode={interactionMode}
        onInteractionModeChange={(mode) => {
          setInteractionMode(mode);
          if (mode === 'select') resetAnalysisState();
        }}
        onOpen3DTerrain={handleOpen3DTerrain}
        onDownloadDem={handleDownloadDem}
        isLoading={isLoading || analysisLoading}
        onLocationFound={(loc) => { setSelectedPoint(loc); if (roiMode === 'polygon') setPolygonPoints([]); }}
        demLoaded={!!demData}
      />

      <LeftSidebar
        layers={layers}
        onToggleLayer={handleToggleLayer}
        demLoaded={!!demData}
        demId={demData?.metadata.dem_id}
        contours={contours}
      />

      <StatsPanel metadata={demData?.metadata || null} />

      {/* Contour Inspector */}
      {selectedContour && !showHydroInspector && !pond && (
        <ContourInspector contour={selectedContour} onClose={() => setSelectedContour(null)} />
      )}

      {/* Hydrology Inspector */}
      {showHydroInspector && (
        <HydrologyInspector
          watershed={watershed}
          droplet={dropletPath}
          onClose={() => { setDropletPath(null); setWatershed(null); setWatershedOutlet(null); }}
        />
      )}

      {/* Pond Inspector */}
      {pond && (
        <PondInspector pond={pond} onClose={() => setPond(null)} />
      )}

      {/* Elevation Profile Modal */}
      {profileData && (
        <ElevationProfileModal
          profileData={profileData}
          onClose={() => { setProfileData(null); setProfileTransect([]); }}
        />
      )}

      {/* 3D Terrain Modal */}
      {is3DOpen && data3D && (
        <Terrain3DModal data3D={data3D} onClose={() => setIs3DOpen(false)} />
      )}

      {/* Loading overlay */}
      {analysisLoading && (
        <div className="absolute bottom-24 left-1/2 -translate-x-1/2 z-[990] flex items-center space-x-2 bg-[#121824]/90 border border-[#1f293d] px-4 py-2 rounded-full text-xs text-slate-300 shadow-xl">
          <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
          <span>Processing terrain analysis...</span>
        </div>
      )}

      {/* Polygon ROI Control Toolbar */}
      {roiMode === 'polygon' && (
        <div className="absolute top-20 right-4 z-[900] bg-[#121824]/95 backdrop-blur-md border border-[#1f293d] rounded-xl p-3 shadow-2xl flex flex-col space-y-2 font-mono text-xs">
          <div className="flex items-center space-x-2 text-slate-200">
            <Hexagon className="w-4 h-4 text-emerald-400" />
            <span className="font-bold">POLYGON ROI</span>
            <span className="bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded text-[10px] border border-emerald-500/30">
              {polygonPoints.length} Vertices
            </span>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleDownloadDem}
              disabled={polygonPoints.length < 3 || isLoading}
              className="flex-1 flex items-center justify-center space-x-1.5 bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-sans font-semibold text-xs px-3 py-1.5 rounded-lg shadow-lg shadow-emerald-500/20 transition-all disabled:opacity-40"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Fetch DEM ({polygonPoints.length} pts)</span>
            </button>

            <button
              onClick={() => setPolygonPoints([])}
              className="p-1.5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-400 border border-rose-500/30 rounded-lg transition-all"
              title="Clear Polygon Vertices"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      <TerrainMap
        selectedPoint={selectedPoint}
        onPointSelect={setSelectedPoint}
        computedBbox={computedBbox}
        roiMode={roiMode}
        polygonPoints={polygonPoints}
        onPolygonPointAdd={(pt) => setPolygonPoints((prev) => [...prev, pt])}
        demData={demData}
        contours={contours}
        selectedContour={selectedContour}
        onSelectContour={setSelectedContour}
        slopeData={slopeData}
        dropletPath={dropletPath}
        watershed={watershed}
        pond={pond}
        profileTransect={profileTransect}
        interactionMode={interactionMode}
        onAnalysisClick={handleAnalysisClick}
        watershedOutlet={watershedOutlet}
        layers={layers}
      />
    </div>
  );
};
