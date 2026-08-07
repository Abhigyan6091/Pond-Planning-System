import axios from 'axios';
import {
  DemRequestPayload, DemResponseData,
  ContourResponseData, BoundingBox,
  SlopeResponseData, DropletPath, WatershedData, LatLng,
  PondResponseData, ElevationProfileResponseData, Terrain3DData, ContourPolylineData,
  FlowVectorsData, StreamNetworkData
} from '../types/terrain';

const API_BASE = '/api';

export const demService = {
  downloadDem: async (payload: DemRequestPayload): Promise<DemResponseData> => {
    const response = await axios.post<DemResponseData>(`${API_BASE}/dem/download-dem`, payload);
    return response.data;
  },

  generateContours: async (
    demId: string,
    elevationMatrix: number[][],
    bounds: BoundingBox,
    interval: number
  ): Promise<ContourResponseData> => {
    const response = await axios.post<ContourResponseData>(`${API_BASE}/contours/generate-contours`, {
      dem_id: demId,
      elevation_matrix: elevationMatrix,
      bounds,
      interval,
    });
    return response.data;
  },

  computeSlope: async (
    demId: string,
    elevationMatrix: number[][],
    bounds: BoundingBox,
    pixelSizeM: number
  ): Promise<SlopeResponseData> => {
    const response = await axios.post<SlopeResponseData>(`${API_BASE}/terrain/slope`, {
      dem_id: demId,
      elevation_matrix: elevationMatrix,
      bounds,
      pixel_size_m: pixelSizeM,
    });
    return response.data;
  },

  simulateDroplet: async (
    startPoint: LatLng,
    elevationMatrix: number[][],
    bounds: BoundingBox,
    pixelSizeM: number
  ): Promise<DropletPath> => {
    const response = await axios.post<DropletPath>(`${API_BASE}/hydrology/flow-droplet`, {
      start_point: startPoint,
      elevation_matrix: elevationMatrix,
      bounds,
      pixel_size_m: pixelSizeM,
    });
    return response.data;
  },

  delineateWatershed: async (
    outletPoint: LatLng,
    elevationMatrix: number[][],
    bounds: BoundingBox,
    pixelSizeM: number
  ): Promise<WatershedData> => {
    const response = await axios.post<WatershedData>(`${API_BASE}/hydrology/watershed`, {
      outlet_point: outletPoint,
      elevation_matrix: elevationMatrix,
      bounds,
      pixel_size_m: pixelSizeM,
    });
    return response.data;
  },

  detectPond: async (
    clickPoint: LatLng,
    elevationMatrix: number[][],
    bounds: BoundingBox,
    pixelSizeM: number
  ): Promise<PondResponseData> => {
    const response = await axios.post<PondResponseData>(`${API_BASE}/analysis/pond`, {
      click_point: clickPoint,
      elevation_matrix: elevationMatrix,
      bounds,
      pixel_size_m: pixelSizeM,
    });
    return response.data;
  },

  computeElevationProfile: async (
    startPoint: LatLng,
    endPoint: LatLng,
    elevationMatrix: number[][],
    bounds: BoundingBox,
    pixelSizeM: number,
    numSamples: number = 100
  ): Promise<ElevationProfileResponseData> => {
    const response = await axios.post<ElevationProfileResponseData>(`${API_BASE}/analysis/elevation-profile`, {
      start_point: startPoint,
      end_point: endPoint,
      elevation_matrix: elevationMatrix,
      bounds,
      pixel_size_m: pixelSizeM,
      num_samples: numSamples,
    });
    return response.data;
  },

  fetchTerrain3D: async (
    elevationMatrix: number[][],
    bounds: BoundingBox,
    demId: string,
    downsample: number = 2
  ): Promise<Terrain3DData> => {
    const response = await axios.post<Terrain3DData>(`${API_BASE}/analysis/terrain-3d`, {
      elevation_matrix: elevationMatrix,
      bounds,
      dem_id: demId,
      downsample,
    });
    return response.data;
  },

  exportContoursGeoJSON: async (demId: string, contours: ContourPolylineData[]) => {
    const response = await axios.post(`${API_BASE}/export/contours/geojson`, {
      dem_id: demId,
      contours,
    }, { responseType: 'blob' });

    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `contours_${demId}.geojson`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  },

  exportContoursCSV: async (demId: string, contours: ContourPolylineData[]) => {
    const response = await axios.post(`${API_BASE}/export/contours/csv`, {
      dem_id: demId,
      contours,
    }, { responseType: 'blob' });

    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `contours_${demId}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  },

  exportProfileCSV: async (profile: any[]) => {
    const response = await axios.post(`${API_BASE}/export/profile/csv`, {
      profile,
    }, { responseType: 'blob' });

    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'elevation_profile.csv');
    document.body.appendChild(link);
    link.click();
    link.remove();
  },

  fetchFlowVectors: async (
    elevationMatrix: number[][],
    bounds: BoundingBox,
    pixelSizeM: number,
    sampleStride: number = 4
  ): Promise<FlowVectorsData> => {
    const response = await axios.post<FlowVectorsData>(`${API_BASE}/hydrology/flow-vectors`, {
      elevation_matrix: elevationMatrix,
      bounds,
      pixel_size_m: pixelSizeM,
      sample_stride: sampleStride,
    });
    return response.data;
  },

  fetchStreamNetwork: async (
    elevationMatrix: number[][],
    bounds: BoundingBox,
    pixelSizeM: number,
    accumulationThreshold: number = 50
  ): Promise<StreamNetworkData> => {
    const response = await axios.post<StreamNetworkData>(`${API_BASE}/hydrology/stream-network`, {
      elevation_matrix: elevationMatrix,
      bounds,
      pixel_size_m: pixelSizeM,
      accumulation_threshold: accumulationThreshold,
    });
    return response.data;
  },

  geocodeLocation: async (query: string): Promise<{ lat: number; lng: number; displayName: string } | null> => {
    try {
      const resp = await axios.get(`https://nominatim.openstreetmap.org/search`, {
        params: { q: query, format: 'json', limit: 1 }
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
  }
};
