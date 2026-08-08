import React from 'react';
import { DemMetadata } from '../types/terrain';
import { ArrowUp, ArrowDown, BarChart2, Database, Layers, Activity } from 'lucide-react';

interface StatsPanelProps {
  metadata: DemMetadata | null;
}

export const StatsPanel: React.FC<StatsPanelProps> = ({ metadata }) => {
  if (!metadata) return null;

  const isRealData = metadata.data_source && !metadata.data_source.includes('Perlin');
  const sourceColor = isRealData ? 'text-emerald-400' : 'text-amber-400';
  const sourceBg    = isRealData ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-amber-500/10 border-amber-500/30';
  const sourceIcon  = isRealData ? '🛰️' : '⚠️';

  return (
    <div className="absolute bottom-6 right-4 z-[900] w-76 bg-[#121824]/95 backdrop-blur-md border border-[#1f293d] rounded-xl p-3.5 shadow-2xl space-y-3"
         style={{ width: '300px' }}>

      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#1f293d] pb-2">
        <div className="flex items-center space-x-2 text-xs font-semibold text-slate-200">
          <BarChart2 className="w-4 h-4 text-cyan-400" />
          <span>TERRAIN STATISTICS</span>
        </div>
        <span className="text-[10px] font-mono text-slate-400">{metadata.width}×{metadata.height} grid</span>
      </div>

      {/* Data Source Debug Panel */}
      <div className={`rounded-lg border px-2.5 py-2 ${sourceBg}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-1.5">
            <Database className={`w-3.5 h-3.5 ${sourceColor}`} />
            <span className="text-[10px] font-semibold text-slate-300 uppercase tracking-wider">Data Source</span>
          </div>
          <span className="text-[9px] font-mono text-slate-400">{metadata.num_api_points ?? (metadata.width * metadata.height)} pts</span>
        </div>
        <div className={`text-xs font-mono font-bold mt-1 ${sourceColor}`}>
          {sourceIcon} {metadata.data_source ?? 'Unknown'}
        </div>
        {!isRealData && (
          <div className="mt-1.5 p-1.5 rounded bg-amber-950/60 border border-amber-500/50 text-[10px] text-amber-200 leading-tight">
            ⚠️ <strong>SYNTHETIC TERRAIN:</strong> Network DEM APIs were unavailable. This elevation data is synthetic and not suitable for engineering analysis.
          </div>
        )}
        <div className="text-[9px] font-mono text-slate-500 mt-1">
          Bounds: {metadata.bounds.south.toFixed(4)}°N, {metadata.bounds.west.toFixed(4)}°E
          → {metadata.bounds.north.toFixed(4)}°N, {metadata.bounds.east.toFixed(4)}°E
        </div>
        <div className="text-[9px] font-mono text-slate-500">
          CRS: {metadata.crs} | Pixel: {metadata.pixel_size_m}m
        </div>
      </div>

      {/* Elevation Stats Grid */}
      <div className="grid grid-cols-2 gap-2 text-xs font-mono">
        <div className="bg-[#0a0d14]/90 p-2 rounded-lg border border-[#1f293d]">
          <div className="flex items-center text-[10px] text-slate-400 space-x-1 mb-0.5">
            <ArrowDown className="w-3 h-3 text-cyan-400" />
            <span>MIN ELEV</span>
          </div>
          <span className="text-sm font-bold text-slate-100">{metadata.min_elevation} m</span>
        </div>

        <div className="bg-[#0a0d14]/90 p-2 rounded-lg border border-[#1f293d]">
          <div className="flex items-center text-[10px] text-slate-400 space-x-1 mb-0.5">
            <ArrowUp className="w-3 h-3 text-rose-400" />
            <span>MAX ELEV</span>
          </div>
          <span className="text-sm font-bold text-slate-100">{metadata.max_elevation} m</span>
        </div>

        <div className="bg-[#0a0d14]/90 p-2 rounded-lg border border-[#1f293d]">
          <div className="flex items-center text-[10px] text-slate-400 space-x-1 mb-0.5">
            <Activity className="w-3 h-3 text-emerald-400" />
            <span>MEAN ELEV</span>
          </div>
          <span className="text-xs font-semibold text-emerald-400">{metadata.mean_elevation} m</span>
        </div>

        <div className="bg-[#0a0d14]/90 p-2 rounded-lg border border-[#1f293d]">
          <div className="text-[10px] text-slate-400 mb-0.5">MEDIAN ELEV</div>
          <span className="text-xs font-semibold text-amber-400">{metadata.median_elevation} m</span>
        </div>

        <div className="bg-[#0a0d14]/90 p-2 rounded-lg border border-[#1f293d]">
          <div className="text-[10px] text-slate-400 mb-0.5">STD DEVIATION</div>
          <span className="text-xs font-semibold text-purple-400">±{metadata.std_elevation} m</span>
        </div>

        <div className="bg-[#0a0d14]/90 p-2 rounded-lg border border-[#1f293d]">
          <div className="flex items-center text-[10px] text-slate-400 space-x-1 mb-0.5">
            <Layers className="w-3 h-3 text-blue-400" />
            <span>PIXEL SIZE</span>
          </div>
          <span className="text-xs font-semibold text-blue-400">{metadata.pixel_size_m} m</span>
        </div>
      </div>
    </div>
  );
};
