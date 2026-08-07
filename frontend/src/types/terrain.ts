export interface LatLng {
  lat: number;
  lng: number;
}

export interface BoundingBox {
  south: number;
  west: number;
  north: number;
  east: number;
}

export interface PolygonROI {
  coordinates: number[][]; // [lng, lat]
}

export type ROISelectionMode = 'point' | 'rectangle' | 'polygon';
export type MapInteractionMode = 'select' | 'droplet' | 'watershed' | 'pond' | 'profile';
export type DemProvider = 'openzenith' | 'opentopography' | 'opentopodata' | 'auto';

export interface DemRequestPayload {
  center?: LatLng;
  radius_km?: number;
  bbox?: BoundingBox;
  polygon?: PolygonROI;
  provider: DemProvider;
  dem_type: string;
  resolution: number;
}

export interface DemMetadata {
  dem_id: string;
  bounds: BoundingBox;
  width: number;
  height: number;
  min_elevation: number;
  max_elevation: number;
  mean_elevation: number;
  std_elevation: number;
  median_elevation: number;
  pixel_size_m: number;
  crs: string;
  data_source?: string;       // e.g. "OpenZenith GLO-30", "SRTM-30m"
  num_api_points?: number;    // how many elevation points were fetched
}

export interface DemResponseData {
  success: boolean;
  message: string;
  metadata: DemMetadata;
  elevation_matrix: number[][];
  elevation_overlay_url: string;
  hillshade_overlay_url: string;
  histogram: {
    counts: number[];
    bins: number[];
  };
}

export interface ContourPolylineData {
  id: string;
  elevation: number;
  coordinates: number[][];
  length_m: number;
  length_km: number;
  vertex_count: number;
  is_closed: boolean;
  area_m2: number | null;
  area_km2: number | null;
}

export interface ContourResponseData {
  success: boolean;
  dem_id: string;
  interval: number;
  total_contours: number;
  contours: ContourPolylineData[];
}

export interface SlopeResponseData {
  success: boolean;
  slope_heatmap_url: string;
  min_slope_deg: number;
  max_slope_deg: number;
  mean_slope_deg: number;
}

export interface DropletPath {
  success: boolean;
  path: LatLng[];
  path_elevations: number[];
  total_distance_m: number;
  elevation_drop_m: number;
}

export interface WatershedData {
  success: boolean;
  outlet: LatLng;
  catchment_polygon: number[][];   // [lng, lat]
  catchment_area_km2: number;
  catchment_area_m2: number;
  perimeter_km: number;
  avg_slope_deg: number;
}

export interface PondInfo {
  pond_id: string;
  center: LatLng;
  bottom_elevation: number;
  water_level: number;
  max_depth: number;
  surface_area_m2: number;
  surface_area_km2: number;
  volume_m3: number;
  volume_km3: number;
  catchment_cells: number;
}

export interface PondResponseData {
  success: boolean;
  pond: PondInfo | null;
  message: string;
}

export interface ElevationProfilePoint {
  distance_m: number;
  elevation: number;
  lat: number;
  lng: number;
}

export interface ElevationProfileResponseData {
  success: boolean;
  profile: ElevationProfilePoint[];
  total_distance_m: number;
  min_elevation: number;
  max_elevation: number;
  elevation_gain_m: number;
  elevation_loss_m: number;
}

export interface Terrain3DData {
  success: boolean;
  dem_id: string;
  z: number[][];
  x: number[];
  y: number[];
  min_z: number;
  max_z: number;
}

export interface LayerVisibility {
  contours: boolean;
  demOverlay: boolean;
  hillshade: boolean;
  watershed: boolean;
  slopeHeatmap: boolean;
  flowVectors: boolean;
  streamNetwork: boolean;
}

export interface FlowVector {
  lat: number;
  lng: number;
  direction_idx: number;  // 0..7 → E, SE, S, SW, W, NW, N, NE
  slope_deg: number;
}

export interface FlowVectorsData {
  success: boolean;
  vectors: FlowVector[];
}

export interface StreamSegment {
  coordinates: number[][];  // [[lng, lat], ...]
  stream_order: number;
}

export interface StreamNetworkData {
  success: boolean;
  segments: StreamSegment[];
}

