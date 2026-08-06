import React, { useState } from 'react';
import { Search, MapPin, Download, Globe, Box, MousePointer, Hexagon, Activity, Droplets, Waves, Database, TrendingUp } from 'lucide-react';
import { LatLng, ROISelectionMode, DemProvider, MapInteractionMode } from '../types/terrain';
import { demService } from '../services/api';

interface TopToolbarProps {
  selectedPoint: LatLng | null;
  radiusKm: number;
  onRadiusChange: (r: number) => void;
  roiMode: ROISelectionMode;
  onRoiModeChange: (mode: ROISelectionMode) => void;
  provider: DemProvider;
  onProviderChange: (p: DemProvider) => void;
  contourInterval: number;
  onContourIntervalChange: (interval: number) => void;
  interactionMode: MapInteractionMode;
  onInteractionModeChange: (mode: MapInteractionMode) => void;
  onOpen3DTerrain: () => void;
  onDownloadDem: () => void;
  isLoading: boolean;
  onLocationFound: (location: LatLng) => void;
  demLoaded: boolean;
}

export const TopToolbar: React.FC<TopToolbarProps> = ({
  selectedPoint,
  radiusKm,
  onRadiusChange,
  roiMode,
  onRoiModeChange,
  provider,
  onProviderChange,
  contourInterval,
  onContourIntervalChange,
  interactionMode,
  onInteractionModeChange,
  onOpen3DTerrain,
  onDownloadDem,
  isLoading,
  onLocationFound,
  demLoaded,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    const result = await demService.geocodeLocation(searchQuery);
    setIsSearching(false);
    if (result) {
      onLocationFound({ lat: result.lat, lng: result.lng });
    } else {
      alert('Location not found. Try a city, mountain, or landmark.');
    }
  };

  return (
    <header className="absolute top-4 left-4 right-4 z-[1000] flex flex-wrap items-center justify-between gap-2 bg-[#121824]/90 backdrop-blur-md border border-[#1f293d] rounded-xl px-4 py-2 shadow-2xl">
      {/* Brand */}
      <div className="flex items-center space-x-3">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-blue-600 via-cyan-500 to-emerald-400 flex items-center justify-center shadow-lg shadow-blue-500/20">
          <Globe className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
            TERRAIN ANALYZER
          </h1>
          <p className="text-[10px] font-mono text-cyan-400 tracking-wider uppercase">GLO-30 · Slope · Hydrology · Ponds</p>
        </div>
      </div>

      {/* Location Search */}
      <form onSubmit={handleSearch} className="relative flex-1 max-w-xs">
        <input
          type="text"
          placeholder="Search location..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full bg-[#0a0d14]/80 border border-[#1f293d] focus:border-blue-500 text-slate-200 text-xs rounded-lg pl-9 pr-4 py-2 outline-none transition-all placeholder:text-slate-500"
        />
        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
        {isSearching && <div className="absolute right-3 top-2.5 w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />}
      </form>

      {/* ROI Tools */}
      <div className="flex items-center space-x-1 bg-[#0a0d14]/80 p-1 rounded-lg border border-[#1f293d]">
        {([['point', MousePointer, 'Point'], ['rectangle', Box, 'Rect'], ['polygon', Hexagon, 'Poly']] as const).map(
          ([mode, Icon, label]) => (
            <button
              key={mode}
              onClick={() => onRoiModeChange(mode as ROISelectionMode)}
              className={`flex items-center space-x-1 px-2 py-1 rounded text-xs font-medium transition-all ${
                roiMode === mode ? 'bg-blue-600 text-white shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{label}</span>
            </button>
          )
        )}
        {roiMode === 'point' && (
          <div className="flex items-center space-x-1 pl-2 border-l border-[#1f293d]">
            {[1, 2, 5, 10].map((r) => (
              <button key={r} onClick={() => onRadiusChange(r)}
                className={`px-1.5 py-0.5 rounded text-[11px] font-mono ${radiusKm === r ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30' : 'text-slate-400 hover:text-slate-200'}`}>
                {r}km
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Contour Interval */}
      <div className="flex items-center space-x-1 bg-[#0a0d14]/80 px-2 py-1 rounded-lg border border-[#1f293d] text-xs">
        <Activity className="w-3.5 h-3.5 text-emerald-400" />
        {[10, 20, 50, 100].map((intv) => (
          <button key={intv} onClick={() => onContourIntervalChange(intv)}
            className={`px-1.5 py-0.5 rounded text-[11px] font-mono ${contourInterval === intv ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'text-slate-400 hover:text-slate-200'}`}>
            {intv}m
          </button>
        ))}
      </div>

      {/* Analysis Tools & Modes */}
      {demLoaded && (
        <div className="flex items-center space-x-1 bg-[#0a0d14]/80 p-1 rounded-lg border border-[#1f293d]">
          <button
            onClick={() => onInteractionModeChange('select')}
            className={`px-2 py-1 rounded text-xs font-medium flex items-center space-x-1 transition-all ${interactionMode === 'select' ? 'bg-slate-600 text-white' : 'text-slate-400 hover:text-white'}`}
            title="Normal map selection mode"
          >
            <MousePointer className="w-3.5 h-3.5" />
            <span>Select</span>
          </button>

          <button
            onClick={() => onInteractionModeChange('droplet')}
            className={`px-2 py-1 rounded text-xs font-medium flex items-center space-x-1 transition-all ${interactionMode === 'droplet' ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-500/20' : 'text-slate-400 hover:text-white'}`}
            title="Click map to simulate water droplet flowing downhill"
          >
            <Droplets className="w-3.5 h-3.5" />
            <span>Droplet</span>
          </button>

          <button
            onClick={() => onInteractionModeChange('watershed')}
            className={`px-2 py-1 rounded text-xs font-medium flex items-center space-x-1 transition-all ${interactionMode === 'watershed' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20' : 'text-slate-400 hover:text-white'}`}
            title="Click map to delineate upstream watershed catchment"
          >
            <Waves className="w-3.5 h-3.5" />
            <span>Watershed</span>
          </button>

          <button
            onClick={() => onInteractionModeChange('pond')}
            className={`px-2 py-1 rounded text-xs font-medium flex items-center space-x-1 transition-all ${interactionMode === 'pond' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-slate-400 hover:text-white'}`}
            title="Click map to estimate pond depth & storage volume"
          >
            <Database className="w-3.5 h-3.5" />
            <span>Pond</span>
          </button>

          <button
            onClick={() => onInteractionModeChange('profile')}
            className={`px-2 py-1 rounded text-xs font-medium flex items-center space-x-1 transition-all ${interactionMode === 'profile' ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/20' : 'text-slate-400 hover:text-white'}`}
            title="Click start & end points on map to plot elevation profile transect"
          >
            <TrendingUp className="w-3.5 h-3.5" />
            <span>Profile</span>
          </button>

          <button
            onClick={onOpen3DTerrain}
            className="px-2 py-1 rounded text-xs font-medium flex items-center space-x-1 bg-purple-600/80 hover:bg-purple-600 text-white shadow-lg shadow-purple-500/20 transition-all border border-purple-500/40 ml-1"
            title="Launch interactive 3D Surface Engine"
          >
            <Box className="w-3.5 h-3.5 text-purple-200" />
            <span>3D View</span>
          </button>
        </div>
      )}

      {/* Provider + Fetch */}
      <div className="flex items-center space-x-2">
        <select
          value={provider}
          onChange={(e) => onProviderChange(e.target.value as DemProvider)}
          className="bg-[#0a0d14]/80 border border-[#1f293d] text-xs text-slate-300 rounded-lg px-2 py-1.5 outline-none"
        >
          <option value="openzenith">OpenZenith (GLO-30)</option>
          <option value="opentopography">OpenTopography</option>
          <option value="opentopodata">OpenTopoData</option>
        </select>

        {selectedPoint && (
          <div className="hidden xl:flex items-center space-x-1 text-[11px] font-mono bg-[#0a0d14]/80 border border-[#1f293d] px-2 py-1.5 rounded-lg text-slate-300">
            <MapPin className="w-3 h-3 text-rose-400" />
            <span>{selectedPoint.lat.toFixed(4)}°, {selectedPoint.lng.toFixed(4)}°</span>
          </div>
        )}

        <button
          onClick={onDownloadDem}
          disabled={isLoading}
          className="flex items-center space-x-1.5 bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-medium text-xs px-3 py-1.5 rounded-lg shadow-lg shadow-blue-500/25 transition-all disabled:opacity-50"
        >
          {isLoading ? <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <Download className="w-3.5 h-3.5" />}
          <span>Fetch DEM</span>
        </button>
      </div>
    </header>
  );
};
