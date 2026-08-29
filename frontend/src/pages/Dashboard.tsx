import React, { useState, useMemo, useEffect } from 'react';
import {
  LatLng, BoundingBox, ROISelectionMode, DemProvider, LayerVisibility,
  DemResponseData, ContourPolylineData, SlopeResponseData, DropletPath,
  WatershedData, MapInteractionMode, PondInfo, ElevationProfileResponseData, Terrain3DData,
  FlowVectorsData, StreamNetworkData, BasemapType, RainfallData, CandidateSite, SuitabilityResponse,
  ContourAnalysisResponse,
} from '../types/terrain';
import { TopToolbar } from '../components/TopToolbar';
import { LeftSidebar } from '../components/LeftSidebar';
import { StatsPanel } from '../components/StatsPanel';
import { ContourInspector } from '../components/ContourInspector';
import { HydrologyInspector } from '../components/HydrologyInspector';
import { PondInspector } from '../components/PondInspector';
import { ElevationProfileModal } from '../components/ElevationProfileModal';
import { Terrain3DModal } from '../components/Terrain3DModal';
import { RainfallPanel } from '../components/RainfallPanel';
import { CandidateSitesPanel } from '../components/CandidateSitesPanel';
import { RecommendationPanel } from '../components/RecommendationPanel';
import { ContourUploadPanel } from '../components/ContourUploadPanel';
import { DraggablePanel } from '../components/DraggablePanel';
import { TerrainMap } from '../map/TerrainMap';
import { demService } from '../services/api';
import { Download, Trash2, Hexagon, Map, Upload, Eye } from 'lucide-react';

export const Dashboard: React.FC = () => {
  // ─── Analysis anchor ────────────────────────────────────────────────────────
  // `villageCenter` is the user-selected location that drives "Analyze Village".
  // It is set ONLY when the user explicitly picks a location via map click or
  // village search. Clicking a candidate or panning the map MUST NOT mutate it.
  const [villageCenter, setVillageCenter] = useState<LatLng | null>({ lat: 19.8762, lng: 75.3433 });

  // `selectedPoint` is the map view/pan center. It is updated whenever the user
  // selects a candidate, clicks the recommendation, or pans to inspect a site.
  // It is intentionally decoupled from the analysis anchor above.
  const [selectedPoint, setSelectedPoint] = useState<LatLng | null>({ lat: 19.8762, lng: 75.3433 });

  const [villageName, setVillageName] = useState<string>('Aurangabad Region');
  const [radiusKm, setRadiusKm] = useState<number>(2.0);
  const [roiMode, setRoiMode] = useState<ROISelectionMode>('point');
  const [polygonPoints, setPolygonPoints] = useState<LatLng[]>([]);
  const [provider, setProvider] = useState<DemProvider>('openzenith');
  const [basemap, setBasemap] = useState<BasemapType>('satellite');
  const [isLoading, setIsLoading] = useState(false);
  const [demData, setDemData] = useState<DemResponseData | null>(null);

  // --- Phase 2: Contours ---
  const [contourInterval, setContourInterval] = useState<number>(5.0);
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

  // --- Flow Vectors & Stream Network ---
  const [flowVectors, setFlowVectors] = useState<FlowVectorsData | null>(null);
  const [streamNetwork, setStreamNetwork] = useState<StreamNetworkData | null>(null);

  // --- Rainfall & Pond Suitability ---
  const [rainfallData, setRainfallData] = useState<RainfallData | null>(null);
  const [rainfallLoading, setRainfallLoading] = useState(false);
  const [candidateSites, setCandidateSites] = useState<CandidateSite[]>([]);
  const [recommendedSite, setRecommendedSite] = useState<CandidateSite | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateSite | null>(null);
  const [suitabilityLoading, setSuitabilityLoading] = useState(false);

  const [analysisLoading, setAnalysisLoading] = useState(false);

  // --- Phase 2: KML/KMZ terrain input ---
  type TerrainInputMode = 'map' | 'upload';
  const [terrainInputMode, setTerrainInputMode] = useState<TerrainInputMode>('map');
  const [kmlResult, setKmlResult] = useState<ContourAnalysisResponse | null>(null);
  const [isTerrainInputVisible, setIsTerrainInputVisible] = useState<boolean>(true);

  const [layers, setLayers] = useState<LayerVisibility>({
    contours: true,
    demOverlay: true,
    hillshade: true,
    watershed: true,
    slopeHeatmap: false,
    flowVectors: false,
    streamNetwork: true,
    candidateSites: true,
    recommendedSite: true,
  });

  // Bounding box displayed on the map preview is derived from villageCenter so
  // the user always sees the region that "Analyze Village" will actually analyse.
  const computedBbox: BoundingBox | null = useMemo(() => {
    if (!villageCenter) return null;
    const latDelta = radiusKm / 111.0;
    const lngDelta = radiusKm / (111.0 * Math.cos((villageCenter.lat * Math.PI) / 180.0));
    return {
      south: villageCenter.lat - latDelta,
      north: villageCenter.lat + latDelta,
      west: villageCenter.lng - lngDelta,
      east: villageCenter.lng + lngDelta,
    };
  }, [villageCenter, radiusKm]);

  const handleToggleLayer = (key: keyof LayerVisibility) => {
    setLayers((prev) => {
      const nextVal = !prev[key];
      if (nextVal && demData) {
        if (key === 'flowVectors' && !flowVectors) {
          demService.fetchFlowVectors(
            demData.elevation_matrix, demData.metadata.bounds, demData.metadata.pixel_size_m, 2
          ).then(setFlowVectors).catch(console.error);
        }
        if (key === 'streamNetwork' && !streamNetwork) {
          demService.fetchStreamNetwork(
            demData.elevation_matrix, demData.metadata.bounds, demData.metadata.pixel_size_m, 20
          ).then(setStreamNetwork).catch(console.error);
        }
      }
      return { ...prev, [key]: nextVal };
    });
  };

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
    setFlowVectors(null);
    setStreamNetwork(null);
    setCandidateSites([]);
    setRecommendedSite(null);
    setSelectedCandidate(null);

    try {
      const payload: any = { provider, dem_type: 'COP30', resolution: 100 };
      if (roiMode === 'polygon' && polygonPoints.length >= 3) {
        payload.polygon = { coordinates: polygonPoints.map((p) => [p.lng, p.lat]) };
      } else if (villageCenter) {
        // ALWAYS use villageCenter — never selectedPoint — so that candidate
        // clicks between analyses cannot silently shift the analysis region.
        payload.center = villageCenter;
        payload.radius_km = radiusKm;
      }

      const res = await demService.downloadDem(payload);
      setDemData(res);

      // 1. Contours
      const cRes = await demService.generateContours(
        res.metadata.dem_id, res.elevation_matrix, res.metadata.bounds, contourInterval
      );
      setContours(cRes.contours);

      // 2. Slope Heatmap
      const sRes = await demService.computeSlope(
        res.metadata.dem_id, res.elevation_matrix, res.metadata.bounds, res.metadata.pixel_size_m
      );
      setSlopeData(sRes);

      // 3. Flow vectors & stream network (background)
      demService.fetchFlowVectors(
        res.elevation_matrix, res.metadata.bounds, res.metadata.pixel_size_m, 2
      ).then(setFlowVectors).catch(console.error);

      demService.fetchStreamNetwork(
        res.elevation_matrix, res.metadata.bounds, res.metadata.pixel_size_m, 20
      ).then(setStreamNetwork).catch(console.error);

      // 4. Fetch Rainfall from Open-Meteo
      // Use villageCenter for the rainfall lookup so it matches the analysis region.
      const latVal = villageCenter ? villageCenter.lat : res.metadata.bounds.south;
      const lngVal = villageCenter ? villageCenter.lng : res.metadata.bounds.west;
      setRainfallLoading(true);
      let rfRes: RainfallData | null = null;
      try {
        rfRes = await demService.fetchRainfall(latVal, lngVal);
        setRainfallData(rfRes);
      } catch (rfErr) {
        console.error('Rainfall fetch failed:', rfErr);
      } finally {
        setRainfallLoading(false);
      }

      // 5. Compute Candidate Pond Sites & Suitability Scoring
      setSuitabilityLoading(true);
      try {
        const rfMm = rfRes && rfRes.annual_avg_mm ? rfRes.annual_avg_mm : undefined;
        const suitRes = await demService.analyzeSuitability(
          res.elevation_matrix, res.metadata.bounds, res.metadata.pixel_size_m, 10, rfMm
        );
        if (suitRes.success) {
          setCandidateSites(suitRes.candidates);
          setRecommendedSite(suitRes.recommended);
          setSelectedCandidate(suitRes.recommended);
        }
      } catch (suitErr) {
        console.error('Suitability analysis failed:', suitErr);
      } finally {
        setSuitabilityLoading(false);
      }

    } catch (err) {
      console.error(err);
      alert('Error fetching DEM or analyzing village. Make sure backend server is active.');
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

  const handleGenerateReport = async () => {
    if (!demData || !selectedPoint) return;
    try {
      const html = await demService.generateReport({
        village_name: villageName,
        lat: selectedPoint.lat,
        lng: selectedPoint.lng,
        roi_radius_km: radiusKm,
        dem_stats: demData.metadata,
        rainfall: rainfallData,
        catchment: watershed,
        recommended_site: recommendedSite,
        candidates: candidateSites,
        data_source: demData.metadata.data_source || 'OpenTopography COP30',
      });

      const reportWindow = window.open('', '_blank');
      if (reportWindow) {
        reportWindow.document.write(html);
        reportWindow.document.close();
      }
    } catch (err) {
      console.error('Report error:', err);
      alert('Failed to generate report. Check console for details.');
    }
  };

  const showHydroInspector = !!(dropletPath || watershed);

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-[#0a0d14]">
      <TopToolbar
        villageCenter={villageCenter}
        villageName={villageName}
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
        isLoading={isLoading || analysisLoading || rainfallLoading || suitabilityLoading}
        onLocationFound={(loc, name) => {
          // Explicit location selection → update BOTH the analysis anchor and the
          // map view centre so the map pans to the newly chosen village.
          setVillageCenter(loc);
          setSelectedPoint(loc);
          if (name) setVillageName(name);
          if (roiMode === 'polygon') setPolygonPoints([]);
        }}
        demLoaded={!!demData}
        basemap={basemap}
        onBasemapChange={setBasemap}
        onGenerateReport={handleGenerateReport}
      />

      <LeftSidebar
        layers={layers}
        onToggleLayer={handleToggleLayer}
        demLoaded={!!demData}
        demId={demData?.metadata.dem_id}
        contours={contours}
        watershed={watershed}
      />

      <StatsPanel metadata={demData?.metadata || null} />

      {/* Rainfall Panel */}
      <RainfallPanel
        rainfall={rainfallData}
        isLoading={rainfallLoading}
        onClose={() => setRainfallData(null)}
      />

      {/* Candidate Sites Panel */}
      {demData && (
        <CandidateSitesPanel
          candidates={candidateSites}
          selectedSite={selectedCandidate}
          onSelectSite={(site) => {
            setSelectedCandidate(site);
            // Pan the map to the candidate — but DO NOT touch villageCenter.
            setSelectedPoint({ lat: site.lat, lng: site.lng });
          }}
          isLoading={suitabilityLoading}
          onClose={() => setCandidateSites([])}
        />
      )}

      {/* Recommendation Panel */}
      {recommendedSite && layers.recommendedSite && (
        <RecommendationPanel
          recommended={recommendedSite}
          onClose={() => setLayers(prev => ({ ...prev, recommendedSite: false }))}
          onSelectOnMap={(site) => {
            // Pan to recommendation — but DO NOT touch villageCenter.
            setSelectedPoint({ lat: site.lat, lng: site.lng });
          }}
        />
      )}

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
      {(analysisLoading || suitabilityLoading || rainfallLoading) && (
        <div className="absolute bottom-24 left-1/2 -translate-x-1/2 z-[990] flex items-center space-x-2 bg-[#121824]/90 border border-[#1f293d] px-4 py-2 rounded-full text-xs text-slate-300 shadow-xl font-mono">
          <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
          <span>
            {rainfallLoading ? 'Fetching rainfall from Open-Meteo...' :
             suitabilityLoading ? 'Evaluating terrain suitability & candidate sites...' :
             'Processing spatial analysis...'}
          </span>
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

      {/* ── Phase 2: Terrain Input Mode Switcher (Draggable & Minimizable) ── */}
      {isTerrainInputVisible ? (
        <DraggablePanel
          id="terrain-input-panel"
          title="TERRAIN INPUT"
          subtitle={terrainInputMode === 'map' ? 'Satellite DEM Selection' : 'Upload Vector Contours'}
          icon={terrainInputMode === 'map' ? <Map className="w-4 h-4 text-cyan-400" /> : <Upload className="w-4 h-4 text-emerald-400" />}
          initialPosition={{ top: 80, right: 16 }}
          width="320px"
          onClose={() => setIsTerrainInputVisible(false)}
          zIndex={930}
        >
          {/* Tab header */}
          <div className="flex border-b border-[#1f293d] -mt-1 -mx-1 mb-2 bg-[#0a0d14]/60 rounded-lg p-0.5">
            <button
              id="tab-select-map"
              onClick={() => setTerrainInputMode('map')}
              className={`flex-1 flex items-center justify-center space-x-1.5 py-1.5 text-[11px] font-mono font-semibold rounded-md transition-all ${
                terrainInputMode === 'map'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Map className="w-3.5 h-3.5" />
              <span>Select from Map</span>
            </button>
            <button
              id="tab-upload-contours"
              onClick={() => setTerrainInputMode('upload')}
              className={`flex-1 flex items-center justify-center space-x-1.5 py-1.5 text-[11px] font-mono font-semibold rounded-md transition-all ${
                terrainInputMode === 'upload'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Upload className="w-3.5 h-3.5" />
              <span>Upload Contours</span>
            </button>
          </div>

          {/* Tab content */}
          <div>
            {terrainInputMode === 'map' ? (
              <div className="space-y-2 text-[10px] font-mono text-slate-400 leading-relaxed bg-[#0a0d14]/60 p-2.5 rounded-lg border border-[#1f293d]">
                <p>
                  📍 Click anywhere on the map to set a location, choose your ROI mode (Point / Rect / Poly), then click{' '}
                  <span className="text-cyan-400 font-semibold">Analyze Village</span> in the toolbar.
                </p>
                <p className="text-slate-500">
                  Fetches real 30m Digital Elevation Models (GLO-30 / COP30 / SRTM) from OpenZenith & OpenTopography.
                </p>
              </div>
            ) : (
              <ContourUploadPanel
                onAnalysisComplete={async (res) => {
                  setKmlResult(res);
                  // KML upload: pan map to pond site if available.
                  // The KML workflow is independent of villageCenter — it provides
                  // its own terrain, so only the map view is updated.
                  if (res.pond_site) {
                    setSelectedPoint({ lat: res.pond_site.latitude, lng: res.pond_site.longitude });
                  }
                  // Synchronize full DEM state with application
                  if (res.elevation_matrix && res.terrain && res.dem_id) {
                    const reconstructedDem: DemResponseData = {
                      success: true,
                      message: `Reconstructed DEM from ${res.input?.filename || 'KML'}`,
                      metadata: {
                        dem_id: res.dem_id,
                        bounds: {
                          south: res.terrain.bounds.min_lat,
                          west: res.terrain.bounds.min_lon,
                          north: res.terrain.bounds.max_lat,
                          east: res.terrain.bounds.max_lon,
                        },
                        width: res.terrain.grid_cols,
                        height: res.terrain.grid_rows,
                        min_elevation: res.terrain.min_elevation_m,
                        max_elevation: res.terrain.max_elevation_m,
                        mean_elevation: res.terrain.mean_elevation_m,
                        std_elevation: 0,
                        median_elevation: res.terrain.mean_elevation_m,
                        pixel_size_m: res.terrain.pixel_size_m,
                        crs: 'EPSG:4326',
                        data_source: `KML Survey Contours (${res.input?.filename || 'Uploaded'})`,
                        is_synthetic: false,
                      },
                      elevation_matrix: res.elevation_matrix,
                      elevation_overlay_url: res.elevation_overlay_url || '',
                      hillshade_overlay_url: res.hillshade_overlay_url || '',
                      histogram: { counts: [], bins: [] },
                    };
                    setDemData(reconstructedDem);

                    // Generate dense contours matching the survey on this DEM
                    try {
                      const cRes = await demService.generateContours(
                        res.dem_id,
                        res.elevation_matrix,
                        reconstructedDem.metadata.bounds,
                        contourInterval
                      );
                      setContours(cRes.contours);
                    } catch (cErr) {
                      console.error('Contour generation error on KML DEM:', cErr);
                    }

                    // Compute slope heatmap on KML DEM
                    try {
                      const sRes = await demService.computeSlope(
                        res.dem_id,
                        res.elevation_matrix,
                        reconstructedDem.metadata.bounds,
                        res.terrain.pixel_size_m
                      );
                      setSlopeData(sRes);
                    } catch (sErr) {
                      console.error('Slope error on KML DEM:', sErr);
                    }

                    // Stream network on KML DEM
                    demService.fetchStreamNetwork(
                      res.elevation_matrix,
                      reconstructedDem.metadata.bounds,
                      res.terrain.pixel_size_m,
                      20
                    ).then(setStreamNetwork).catch(console.error);

                    // Populate Candidate Sites & Recommended Site
                    if (res.candidates && res.candidates.length > 0) {
                      setCandidateSites(res.candidates);
                      setRecommendedSite(res.candidates[0]);
                      setSelectedCandidate(res.candidates[0]);
                    }

                    // Populate Catchment
                    if (res.catchment && res.pond_site) {
                      setWatershed({
                        success: true,
                        outlet: { lat: res.pond_site.latitude, lng: res.pond_site.longitude },
                        catchment_polygon: res.catchment.boundary,
                        catchment_area_km2: res.catchment.area_km2,
                        catchment_area_m2: res.catchment.area_m2,
                        perimeter_km: res.catchment.perimeter_km,
                        avg_slope_deg: res.catchment.avg_slope_deg,
                      });
                      setWatershedOutlet({ lat: res.pond_site.latitude, lng: res.pond_site.longitude });
                    }
                  }
                }}
                onClose={() => setKmlResult(null)}
              />
            )}
          </div>
        </DraggablePanel>
      ) : (
        <button
          onClick={() => setIsTerrainInputVisible(true)}
          className="absolute top-20 right-4 z-[900] bg-[#121824]/90 backdrop-blur-md border border-[#1f293d] hover:border-cyan-500/40 text-slate-300 hover:text-white px-3 py-2 rounded-xl text-xs font-mono font-semibold flex items-center space-x-2 shadow-xl transition-all"
        >
          <Upload className="w-4 h-4 text-cyan-400" />
          <span>Show Terrain Input</span>
        </button>
      )}

      <TerrainMap
        selectedPoint={selectedPoint}
        onPointSelect={(pt) => {
          // A direct map click is an explicit new analysis location selection.
          // Update both the analysis anchor and the map view.
          setVillageCenter(pt);
          setSelectedPoint(pt);
        }}
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
        flowVectors={flowVectors}
        streamNetwork={streamNetwork}
        basemap={basemap}
        candidateSites={candidateSites}
        recommendedSite={recommendedSite}
        kmlResult={kmlResult}
        onCandidateClick={(site) => {
          setSelectedCandidate(site);
          // Pan map to clicked candidate — DO NOT touch villageCenter.
          setSelectedPoint({ lat: site.lat, lng: site.lng });
        }}
      />
    </div>
  );
};
