import React, { useState, useMemo, useEffect } from 'react';
import {
  LatLng, BoundingBox, ROISelectionMode, DemProvider, LayerVisibility,
  DemResponseData, ContourPolylineData, SlopeResponseData, DropletPath,
  WatershedData, MapInteractionMode, PondInfo, ElevationProfileResponseData, Terrain3DData,
  FlowVectorsData, StreamNetworkData, BasemapType, RainfallData, CandidateSite, SuitabilityResponse,
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
import { TerrainMap } from '../map/TerrainMap';
import { demService } from '../services/api';
import { Download, Trash2, Hexagon } from 'lucide-react';

export const Dashboard: React.FC = () => {
  // --- ROI / DEM state ---
  const [selectedPoint, setSelectedPoint] = useState<LatLng | null>({ lat: 19.8762, lng: 75.3433 }); // Aurangabad, Maharashtra
  const [villageName, setVillageName] = useState<string>('Aurangabad Region');
  const [radiusKm, setRadiusKm] = useState<number>(2.0);
  const [roiMode, setRoiMode] = useState<ROISelectionMode>('point');
  const [polygonPoints, setPolygonPoints] = useState<LatLng[]>([]);
  const [provider, setProvider] = useState<DemProvider>('openzenith');
  const [basemap, setBasemap] = useState<BasemapType>('satellite');
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
      } else if (selectedPoint) {
        payload.center = selectedPoint;
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
      const latVal = selectedPoint ? selectedPoint.lat : res.metadata.bounds.south;
      const lngVal = selectedPoint ? selectedPoint.lng : res.metadata.bounds.west;
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
        selectedPoint={selectedPoint}
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
          onSelectOnMap={(site) => setSelectedPoint({ lat: site.lat, lng: site.lng })}
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
        flowVectors={flowVectors}
        streamNetwork={streamNetwork}
        basemap={basemap}
        candidateSites={candidateSites}
        recommendedSite={recommendedSite}
        onCandidateClick={(site) => {
          setSelectedCandidate(site);
          setSelectedPoint({ lat: site.lat, lng: site.lng });
        }}
      />
    </div>
  );
};
