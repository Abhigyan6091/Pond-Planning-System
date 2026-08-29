import React, { useState } from 'react';
import {
  Search, MapPin, Download, Globe, Box, MousePointer, Hexagon,
  Activity, Droplets, Waves, Database, TrendingUp, Map, Satellite,
  FileText, Settings,
} from 'lucide-react';
import {
  LatLng, ROISelectionMode, DemProvider, MapInteractionMode, BasemapType,
} from '../types/terrain';
import { demService } from '../services/api';

interface TopToolbarProps {
  villageCenter: LatLng | null;
  villageName: string;
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
  onLocationFound: (location: LatLng, name: string) => void;
  demLoaded: boolean;
  basemap: BasemapType;
  onBasemapChange: (b: BasemapType) => void;
  onGenerateReport: () => void;
}

export const TopToolbar: React.FC<TopToolbarProps> = ({
  villageCenter, villageName, radiusKm, onRadiusChange, roiMode, onRoiModeChange,
  provider, onProviderChange, contourInterval, onContourIntervalChange,
  interactionMode, onInteractionModeChange, onOpen3DTerrain, onDownloadDem,
  isLoading, onLocationFound, demLoaded, basemap, onBasemapChange, onGenerateReport,
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
      onLocationFound({ lat: result.lat, lng: result.lng }, result.displayName.split(',')[0]);
      setSearchQuery(result.displayName.split(',')[0]);
    } else {
      alert('Location not found. Try a village, city, or landmark.');
    }
  };

  const basemapOptions: { id: BasemapType; label: string; icon: React.ReactNode }[] = [
    { id: 'osm',       label: 'Street',    icon: <Map className="w-3.5 h-3.5" /> },
    { id: 'satellite', label: 'Satellite', icon: <Satellite className="w-3.5 h-3.5" /> },
    { id: 'terrain',   label: 'Topo',      icon: <Globe className="w-3.5 h-3.5" /> },
  ];

  return (
    <header className="absolute top-4 left-4 right-4 z-[1000] flex flex-wrap items-center justify-between gap-2 bg-[#0d1117]/92 backdrop-blur-md border border-[#1f293d] rounded-xl px-4 py-2 shadow-2xl">
      {/* Brand */}
      <div className="flex items-center space-x-3 shrink-0">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-blue-600 via-cyan-500 to-emerald-400 flex items-center justify-center shadow-lg shadow-blue-500/20">
          <Waves className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent leading-tight">
            Village Pond Planning
          </h1>
          <p className="text-[10px] font-mono text-cyan-400 tracking-wider uppercase leading-tight">
            {villageName || 'AI / GIS · Terrain · Hydrology · Rainfall'}
          </p>
        </div>
      </div>

      {/* Village Search */}
      <form onSubmit={handleSearch} className="relative flex-1 max-w-xs">
        <input
          type="text"
          placeholder="Search village or location..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full bg-[#0a0d14]/80 border border-[#1f293d] focus:border-cyan-500/60 text-slate-200 text-xs rounded-lg pl-9 pr-4 py-2 outline-none transition-all placeholder:text-slate-500"
        />
        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
        {isSearching && <div className="absolute right-3 top-2.5 w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />}
      </form>

      {/* Basemap Toggle */}
      <div className="flex items-center space-x-0.5 bg-[#0a0d14]/80 p-1 rounded-lg border border-[#1f293d]">
        {basemapOptions.map(({ id, label, icon }) => (
          <button
            key={id}
            onClick={() => onBasemapChange(id)}
            className={`flex items-center space-x-1 px-2 py-1 rounded text-xs font-medium transition-all ${
              basemap === id ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-white'
            }`}
          >
            {icon}<span>{label}</span>
          </button>
        ))}
      </div>

      {/* ROI Mode */}
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
        <span className="text-[10px] text-slate-400 font-mono hidden sm:inline">Interval:</span>
        {[1, 2, 5, 10, 20, 50].map((intv) => (
          <button key={intv} onClick={() => onContourIntervalChange(intv)}
            className={`px-1.5 py-0.5 rounded text-[11px] font-mono font-medium transition-all ${contourInterval === intv ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm shadow-emerald-500/20' : 'text-slate-400 hover:text-slate-200'}`}>
            {intv}m
          </button>
        ))}
      </div>

      {/* Analysis Tools */}
      {demLoaded && (
        <div className="flex items-center space-x-1 bg-[#0a0d14]/80 p-1 rounded-lg border border-[#1f293d]">
          {[
            { mode: 'select',    Icon: MousePointer, label: 'Select',    color: 'bg-slate-600' },
            { mode: 'droplet',   Icon: Droplets,     label: 'Droplet',   color: 'bg-cyan-600 shadow-cyan-500/20' },
            { mode: 'watershed', Icon: Waves,         label: 'Watershed', color: 'bg-indigo-600 shadow-indigo-500/20' },
            { mode: 'pond',      Icon: Database,      label: 'Pond',      color: 'bg-blue-600 shadow-blue-500/20' },
            { mode: 'profile',   Icon: TrendingUp,    label: 'Profile',   color: 'bg-emerald-600 shadow-emerald-500/20' },
          ].map(({ mode, Icon, label, color }) => (
            <button
              key={mode}
              onClick={() => onInteractionModeChange(mode as MapInteractionMode)}
              title={label}
              className={`px-2 py-1 rounded text-xs font-medium flex items-center space-x-1 transition-all shadow-lg ${
                interactionMode === mode ? `${color} text-white` : 'text-slate-400 hover:text-white'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span className="hidden xl:inline">{label}</span>
            </button>
          ))}
          <button
            onClick={onOpen3DTerrain}
            className="px-2 py-1 rounded text-xs font-medium flex items-center space-x-1 bg-purple-600/80 hover:bg-purple-600 text-white shadow-lg shadow-purple-500/20 transition-all border border-purple-500/40 ml-1"
            title="3D Terrain View"
          >
            <Box className="w-3.5 h-3.5 text-purple-200" />
            <span className="hidden xl:inline">3D View</span>
          </button>
        </div>
      )}

      {/* Provider + Actions */}
      <div className="flex items-center space-x-2 shrink-0">
        <select
          value={provider}
          onChange={(e) => onProviderChange(e.target.value as DemProvider)}
          className="bg-[#0a0d14]/80 border border-[#1f293d] text-xs text-slate-300 rounded-lg px-2 py-1.5 outline-none"
        >
          <option value="openzenith">OpenZenith (GLO-30)</option>
          <option value="opentopography">OpenTopography</option>
          <option value="opentopodata">OpenTopoData</option>
        </select>

        {villageCenter && (
          <div className="hidden 2xl:flex items-center space-x-1 text-[11px] font-mono bg-[#0a0d14]/80 border border-[#1f293d] px-2 py-1.5 rounded-lg text-slate-300">
            <MapPin className="w-3 h-3 text-rose-400" />
            <span>{villageCenter.lat.toFixed(4)}°, {villageCenter.lng.toFixed(4)}°</span>
          </div>
        )}

        {demLoaded && (
          <button
            onClick={onGenerateReport}
            className="flex items-center space-x-1.5 bg-[#1a2332] hover:bg-[#1f2d45] border border-slate-600/40 text-slate-300 hover:text-white font-medium text-xs px-3 py-1.5 rounded-lg transition-all"
            title="Generate Analysis Report"
          >
            <FileText className="w-3.5 h-3.5 text-violet-400" />
            <span className="hidden lg:inline">Report</span>
          </button>
        )}

        <button
          onClick={onDownloadDem}
          disabled={isLoading}
          className="flex items-center space-x-1.5 bg-gradient-to-r from-emerald-600 to-cyan-500 hover:from-emerald-500 hover:to-cyan-400 text-white font-semibold text-xs px-3 py-1.5 rounded-lg shadow-lg shadow-emerald-500/20 transition-all disabled:opacity-50"
        >
          {isLoading
            ? <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            : <Download className="w-3.5 h-3.5" />}
          <span>Analyze Village</span>
        </button>
      </div>
    </header>
  );
};
