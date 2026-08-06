import React from 'react';
import { PondInfo } from '../types/terrain';
import { Database, Waves, X, Layers, Maximize2, ArrowDownCircle, ArrowUpCircle } from 'lucide-react';

interface PondInspectorProps {
  pond: PondInfo;
  onClose: () => void;
}

export const PondInspector: React.FC<PondInspectorProps> = ({ pond, onClose }) => {
  return (
    <div className="absolute top-20 right-4 z-[950] w-84 bg-[#121824]/95 backdrop-blur-md border border-[#1f293d] rounded-xl p-4 shadow-2xl space-y-3.5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#1f293d] pb-2.5">
        <div className="flex items-center space-x-2">
          <div className="w-6 h-6 rounded-md bg-blue-500/20 border border-blue-500/40 flex items-center justify-center">
            <Database className="w-3.5 h-3.5 text-blue-400" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-slate-100">POND ANALYSIS</h3>
            <p className="text-[10px] font-mono text-blue-400">Depression Depth & Storage Volume</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-200 p-1 rounded-md hover:bg-slate-800 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Main Metrics */}
      <div className="grid grid-cols-2 gap-2 text-xs font-mono">
        <div className="bg-blue-950/30 p-2.5 rounded-lg border border-blue-500/30">
          <div className="text-[10px] text-slate-400 mb-0.5">STORAGE VOLUME</div>
          <span className="text-sm font-bold text-blue-400">{pond.volume_m3.toLocaleString()} m³</span>
          <div className="text-[9px] text-slate-400 font-sans mt-0.5">({pond.volume_km3.toFixed(6)} km³)</div>
        </div>

        <div className="bg-cyan-950/30 p-2.5 rounded-lg border border-cyan-500/30">
          <div className="text-[10px] text-slate-400 mb-0.5">MAX POND DEPTH</div>
          <span className="text-sm font-bold text-cyan-300">{pond.max_depth} m</span>
          <div className="text-[9px] text-slate-400 font-sans mt-0.5">from spill edge</div>
        </div>
      </div>

      {/* Secondary Metrics */}
      <div className="grid grid-cols-2 gap-2 text-xs font-mono">
        <div className="bg-[#0a0d14]/90 p-2.5 rounded-lg border border-[#1f293d]">
          <div className="flex items-center space-x-1 text-[10px] text-slate-400 mb-0.5">
            <Maximize2 className="w-3 h-3 text-emerald-400" />
            <span>SURFACE AREA</span>
          </div>
          <span className="text-xs font-semibold text-emerald-400">{pond.surface_area_m2.toLocaleString()} m²</span>
        </div>

        <div className="bg-[#0a0d14]/90 p-2.5 rounded-lg border border-[#1f293d]">
          <div className="flex items-center space-x-1 text-[10px] text-slate-400 mb-0.5">
            <Layers className="w-3 h-3 text-indigo-400" />
            <span>GRID CELLS</span>
          </div>
          <span className="text-xs font-semibold text-slate-200">{pond.catchment_cells} cells</span>
        </div>
      </div>

      {/* Elevations */}
      <div className="bg-[#0a0d14]/80 border border-[#1f293d] p-2.5 rounded-lg space-y-1.5 font-mono text-xs">
        <div className="flex items-center justify-between text-slate-300">
          <div className="flex items-center space-x-1 text-[10px] text-slate-400">
            <ArrowUpCircle className="w-3 h-3 text-sky-400" />
            <span>Water Level (Spill Rim)</span>
          </div>
          <span className="font-bold text-sky-300">{pond.water_level} m</span>
        </div>
        <div className="flex items-center justify-between text-slate-300">
          <div className="flex items-center space-x-1 text-[10px] text-slate-400">
            <ArrowDownCircle className="w-3 h-3 text-amber-400" />
            <span>Bottom Elevation</span>
          </div>
          <span className="font-bold text-amber-300">{pond.bottom_elevation} m</span>
        </div>
      </div>
    </div>
  );
};
