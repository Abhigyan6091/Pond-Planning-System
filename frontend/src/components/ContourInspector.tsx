import React from 'react';
import { ContourPolylineData } from '../types/terrain';
import { Activity, Ruler, Maximize2, Hash, X, CheckCircle, AlertCircle } from 'lucide-react';

interface ContourInspectorProps {
  contour: ContourPolylineData | null;
  onClose: () => void;
}

export const ContourInspector: React.FC<ContourInspectorProps> = ({ contour, onClose }) => {
  if (!contour) return null;

  return (
    <div className="absolute top-20 right-4 z-[950] w-80 bg-[#121824]/95 backdrop-blur-md border border-[#1f293d] rounded-xl p-4 shadow-2xl space-y-3.5 transition-all">
      {/* Card Header */}
      <div className="flex items-center justify-between border-b border-[#1f293d] pb-2.5">
        <div className="flex items-center space-x-2">
          <div className="w-6 h-6 rounded-md bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center">
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-slate-100">CONTOUR INSPECTOR</h3>
            <p className="text-[10px] font-mono text-cyan-400">Selected Polyline ID: {contour.id}</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-200 p-1 rounded-md hover:bg-slate-800 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* FEATURE 1: Elevation, Arc Length, Vertices */}
      <div className="space-y-2">
        <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
          Feature 1: Spatial Measurements
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs font-mono">
          <div className="bg-[#0a0d14]/90 p-2.5 rounded-lg border border-[#1f293d]">
            <div className="text-[10px] text-slate-400 mb-0.5">ELEVATION</div>
            <span className="text-sm font-bold text-cyan-400">{contour.elevation} m</span>
          </div>

          <div className="bg-[#0a0d14]/90 p-2.5 rounded-lg border border-[#1f293d]">
            <div className="flex items-center space-x-1 text-[10px] text-slate-400 mb-0.5">
              <Hash className="w-3 h-3 text-slate-400" />
              <span>VERTICES</span>
            </div>
            <span className="text-sm font-bold text-slate-200">{contour.vertex_count} pts</span>
          </div>
        </div>

        <div className="bg-[#0a0d14]/90 p-2.5 rounded-lg border border-[#1f293d] flex items-center justify-between font-mono">
          <div className="flex items-center space-x-2">
            <Ruler className="w-4 h-4 text-emerald-400" />
            <div>
              <div className="text-[10px] text-slate-400">ARC LENGTH</div>
              <div className="text-xs font-bold text-emerald-400">{contour.length_km} km</div>
            </div>
          </div>
          <span className="text-[11px] text-slate-400 font-mono">({contour.length_m} m)</span>
        </div>
      </div>

      {/* FEATURE 2: Enclosed Area Calculation */}
      <div className="space-y-2 border-t border-[#1f293d] pt-2.5">
        <div className="flex items-center justify-between text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
          <span>Feature 2: Enclosed Area</span>
          {contour.is_closed ? (
            <span className="flex items-center space-x-1 text-emerald-400">
              <CheckCircle className="w-3 h-3" />
              <span>Closed Loop</span>
            </span>
          ) : (
            <span className="flex items-center space-x-1 text-amber-400">
              <AlertCircle className="w-3 h-3" />
              <span>Open Line</span>
            </span>
          )}
        </div>

        {contour.is_closed && contour.area_m2 !== null ? (
          <div className="bg-emerald-950/30 border border-emerald-500/30 p-2.5 rounded-lg font-mono space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-300">Surface Area (km²):</span>
              <span className="text-sm font-bold text-emerald-400">{contour.area_km2} km²</span>
            </div>
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span>Surface Area (m²):</span>
              <span>{contour.area_m2?.toLocaleString()} m²</span>
            </div>
          </div>
        ) : (
          <div className="bg-[#0a0d14]/60 border border-[#1f293d] p-2.5 rounded-lg text-xs text-slate-400 font-mono">
            Contour does not form a closed polygon boundary. Area calculation applies to closed loops.
          </div>
        )}
      </div>
    </div>
  );
};
