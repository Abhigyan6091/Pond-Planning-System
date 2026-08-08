import axios from 'axios';
import {
  DemRequestPayload, DemResponseData,
  ContourResponseData, BoundingBox,
  SlopeResponseData, DropletPath, WatershedData, LatLng,
  PondResponseData, ElevationProfileResponseData, Terrain3DData, ContourPolylineData,
  FlowVectorsData, StreamNetworkData,
  RainfallData, RunoffData, SuitabilityResponse, CandidateSite,
} from '../types/terrain';

const API_BASE = '/api';

export const demService = {
  downloadDem: async (payload: DemRequestPayload): Promise<DemResponseData> => {
    const response = await axios.post<DemResponseData>(`${API_BASE}/dem/download-dem`, payload);
    return response.data;
  },

  generateContours: async (
    demId: string, elevationMatrix: number[][], bounds: BoundingBox, interval: number
  ): Promise<ContourResponseData> => {
    const response = await axios.post<ContourResponseData>(`${API_BASE}/contours/generate-contours`, {
      dem_id: demId, elevation_matrix: elevationMatrix, bounds, interval,
    });
    return response.data;
  },

  computeSlope: async (
    demId: string, elevationMatrix: number[][], bounds: BoundingBox, pixelSizeM: number
  ): Promise<SlopeResponseData> => {
    const response = await axios.post<SlopeResponseData>(`${API_BASE}/terrain/slope`, {
      dem_id: demId, elevation_matrix: elevationMatrix, bounds, pixel_size_m: pixelSizeM,
    });
    return response.data;
  },

  simulateDroplet: async (
    startPoint: LatLng, elevationMatrix: number[][], bounds: BoundingBox, pixelSizeM: number
  ): Promise<DropletPath> => {
    const response = await axios.post<DropletPath>(`${API_BASE}/hydrology/flow-droplet`, {
      start_point: startPoint, elevation_matrix: elevationMatrix, bounds, pixel_size_m: pixelSizeM,
    });
    return response.data;
  },

  delineateWatershed: async (
    outletPoint: LatLng, elevationMatrix: number[][], bounds: BoundingBox, pixelSizeM: number
  ): Promise<WatershedData> => {
    const response = await axios.post<WatershedData>(`${API_BASE}/hydrology/watershed`, {
      outlet_point: outletPoint, elevation_matrix: elevationMatrix, bounds, pixel_size_m: pixelSizeM,
    });
    return response.data;
  },

  detectPond: async (
    clickPoint: LatLng, elevationMatrix: number[][], bounds: BoundingBox, pixelSizeM: number
  ): Promise<PondResponseData> => {
    const response = await axios.post<PondResponseData>(`${API_BASE}/analysis/pond`, {
      click_point: clickPoint, elevation_matrix: elevationMatrix, bounds, pixel_size_m: pixelSizeM,
    });
    return response.data;
  },

  computeElevationProfile: async (
    startPoint: LatLng, endPoint: LatLng, elevationMatrix: number[][],
    bounds: BoundingBox, pixelSizeM: number, numSamples: number = 100
  ): Promise<ElevationProfileResponseData> => {
    const response = await axios.post<ElevationProfileResponseData>(`${API_BASE}/analysis/elevation-profile`, {
      start_point: startPoint, end_point: endPoint, elevation_matrix: elevationMatrix,
      bounds, pixel_size_m: pixelSizeM, num_samples: numSamples,
    });
    return response.data;
  },

  fetchTerrain3D: async (
    elevationMatrix: number[][], bounds: BoundingBox, demId: string, downsample: number = 2
  ): Promise<Terrain3DData> => {
    const response = await axios.post<Terrain3DData>(`${API_BASE}/analysis/terrain-3d`, {
      elevation_matrix: elevationMatrix, bounds, dem_id: demId, downsample,
    });
    return response.data;
  },

  fetchFlowVectors: async (
    elevationMatrix: number[][], bounds: BoundingBox, pixelSizeM: number, sampleStride: number = 4
  ): Promise<FlowVectorsData> => {
    const response = await axios.post<FlowVectorsData>(`${API_BASE}/hydrology/flow-vectors`, {
      elevation_matrix: elevationMatrix, bounds, pixel_size_m: pixelSizeM, sample_stride: sampleStride,
    });
    return response.data;
  },

  fetchStreamNetwork: async (
    elevationMatrix: number[][], bounds: BoundingBox, pixelSizeM: number, accumulationThreshold: number = 50
  ): Promise<StreamNetworkData> => {
    const response = await axios.post<StreamNetworkData>(`${API_BASE}/hydrology/stream-network`, {
      elevation_matrix: elevationMatrix, bounds, pixel_size_m: pixelSizeM, accumulation_threshold: accumulationThreshold,
    });
    return response.data;
  },

  // ── Rainfall ──────────────────────────────────────────────────────
  fetchRainfall: async (
    lat: number, lng: number, startYear: number = 2014, endYear: number = 2023
  ): Promise<RainfallData> => {
    const response = await axios.post<RainfallData>(`${API_BASE}/rainfall/historical`, {
      lat, lng, start_year: startYear, end_year: endYear,
    });
    return response.data;
  },

  // ── Runoff ────────────────────────────────────────────────────────
  estimateRunoff: async (
    rainfallMm: number, catchmentAreaM2: number,
    runoffCoefficient: number = 0.40,
    coefficientPreset?: 'low' | 'medium' | 'high' | 'urban'
  ): Promise<RunoffData> => {
    const response = await axios.post<RunoffData>(`${API_BASE}/runoff/estimate`, {
      rainfall_mm: rainfallMm,
      catchment_area_m2: catchmentAreaM2,
      runoff_coefficient: runoffCoefficient,
      coefficient_preset: coefficientPreset || null,
    });
    return response.data;
  },

  // ── Suitability ───────────────────────────────────────────────────
  analyzeSuitability: async (
    elevationMatrix: number[][], bounds: BoundingBox, pixelSizeM: number,
    numCandidates: number = 10, rainfallMm?: number, runoffCoefficient: number = 0.40
  ): Promise<SuitabilityResponse> => {
    const response = await axios.post<SuitabilityResponse>(`${API_BASE}/suitability/analyze`, {
      elevation_matrix: elevationMatrix, bounds, pixel_size_m: pixelSizeM,
      num_candidates: numCandidates,
      rainfall_mm: rainfallMm || null,
      runoff_coefficient: runoffCoefficient,
    });
    return response.data;
  },

  // ── Export ────────────────────────────────────────────────────────
  exportContoursGeoJSON: async (demId: string, contours: ContourPolylineData[]) => {
    const response = await axios.post(`${API_BASE}/export/contours/geojson`, { dem_id: demId, contours }, { responseType: 'blob' });
    _download(response.data, `contours_${demId}.geojson`);
  },

  exportContoursCSV: async (demId: string, contours: ContourPolylineData[]) => {
    const response = await axios.post(`${API_BASE}/export/contours/csv`, { dem_id: demId, contours }, { responseType: 'blob' });
    _download(response.data, `contours_${demId}.csv`);
  },

  exportProfileCSV: async (profile: any[]) => {
    const response = await axios.post(`${API_BASE}/export/profile/csv`, { profile }, { responseType: 'blob' });
    _download(response.data, 'elevation_profile.csv');
  },

  exportCandidatesCSV: async (candidates: CandidateSite[]) => {
    const response = await axios.post(`${API_BASE}/export/candidates/csv`, { candidates }, { responseType: 'blob' });
    _download(response.data, 'candidate_pond_sites.csv');
  },

  exportCatchmentGeoJSON: async (catchmentPolygon: number[][], properties: Record<string, any> = {}) => {
    const response = await axios.post(`${API_BASE}/export/catchment/geojson`, {
      catchment_polygon: catchmentPolygon, properties,
    }, { responseType: 'blob' });
    _download(response.data, 'catchment.geojson');
  },

  exportPondSitesGeoJSON: async (candidates: CandidateSite[]) => {
    const response = await axios.post(`${API_BASE}/export/pond-sites/geojson`, { candidates }, { responseType: 'blob' });
    _download(response.data, 'pond_sites.geojson');
  },

  // ── Report ────────────────────────────────────────────────────────
  generateReport: async (payload: {
    village_name: string; lat: number; lng: number; roi_radius_km?: number;
    dem_stats?: any; rainfall?: any; catchment?: any; runoff?: any;
    recommended_site?: any; candidates?: any[]; data_source?: string;
  }): Promise<string> => {
    const response = await axios.post(`${API_BASE}/report/generate`, payload, {
      responseType: 'text',
      headers: { 'Accept': 'text/html' },
    });
    return response.data;
  },

  // ── Geocoding ─────────────────────────────────────────────────────
  geocodeLocation: async (query: string): Promise<{ lat: number; lng: number; displayName: string } | null> => {
    try {
      const resp = await axios.get(`https://nominatim.openstreetmap.org/search`, {
        params: { q: query, format: 'json', limit: 1 },
        headers: { 'Accept-Language': 'en' },
      });
      if (resp.data && resp.data.length > 0) {
        const item = resp.data[0];
        return { lat: parseFloat(item.lat), lng: parseFloat(item.lon), displayName: item.display_name };
      }
      return null;
    } catch (err) {
      console.error('Geocoding error:', err);
      return null;
    }
  },
};

function _download(data: any, filename: string) {
  const url = window.URL.createObjectURL(new Blob([data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
