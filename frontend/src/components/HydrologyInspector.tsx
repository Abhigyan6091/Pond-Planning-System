import React from 'react';
import { WatershedData, DropletPath } from '../types/terrain';
import { Waves, Droplets, X, MapPin, Maximize2, TrendingDown, BarChart2 } from 'lucide-react';

interface HydrologyInspectorProps {
  watershed: WatershedData | null;
  droplet: DropletPath | null;
  onClose: () => void;
}

export const HydrologyInspector: React.FC<HydrologyInspectorProps> = ({
  watershed,
  droplet,
  onClose,
}) => {
  if (!watershed && !droplet) return null;

  return (
    <div className="absolute top-20 right-4 z-[950] w-80 bg-[#121824]/95 backdrop-blur-md border border-[#1f293d] rounded-xl p-4 shadow-2xl space-y-3.5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#1f293d] pb-2.5">
        <div className="flex items-center space-x-2">
          <div className="w-6 h-6 rounded-md bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center">
            <Waves className="w-3.5 h-3.5 text-indigo-400" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-slate-100">HYDROLOGY INSPECTOR</h3>
            <p className="text-[10px] font-mono text-indigo-400">
              {watershed ? 'Watershed Catchment' : 'Droplet Flow Trace'}
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-200 p-1 rounded-md hover:bg-slate-800 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Droplet Path Stats */}
      {droplet && (
        <div className="space-y-2">
          <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center space-x-1">
            <Droplets className="w-3.5 h-3.5 text-cyan-400" />
            <span>Water Droplet Flow Trace</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div className="bg-[#0a0d14]/90 p-2.5 rounded-lg border border-[#1f293d]">
              <div className="text-[10px] text-slate-400 mb-0.5">PATH VERTICES</div>
              <span className="text-sm font-bold text-cyan-400">{droplet.path.length}</span>
            </div>
            <div className="bg-[#0a0d14]/90 p-2.5 rounded-lg border border-[#1f293d]">
              <div className="text-[10px] text-slate-400 mb-0.5">DISTANCE</div>
              <span className="text-sm font-bold text-cyan-400">{(droplet.total_distance_m / 1000).toFixed(2)} km</span>
            </div>
          </div>
          <div className="bg-cyan-950/30 border border-cyan-500/30 p-2.5 rounded-lg flex items-center justify-between font-mono">
            <div className="flex items-center space-x-2">
              <TrendingDown className="w-4 h-4 text-cyan-400" />
              <div>
                <div className="text-[10px] text-slate-400">ELEVATION DROP</div>
                <div className="text-xs font-bold text-cyan-300">{droplet.elevation_drop_m} m</div>
              </div>
            </div>
            <span className="text-[11px] text-slate-400">downhill</span>
          </div>
        </div>
      )}

      {/* Watershed Catchment Stats */}
      {watershed && (
        <div className="space-y-2">
          <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center space-x-1">
            <Waves className="w-3.5 h-3.5 text-indigo-400" />
            <span>Feature 6: Catchment Area</span>
          </div>

          <div className="flex items-center space-x-1.5 text-[11px] font-mono text-slate-400 bg-[#0a0d14]/80 px-2.5 py-1.5 rounded-lg border border-[#1f293d]">
            <MapPin className="w-3 h-3 text-rose-400" />
            <span>Outlet: {watershed.outlet.lat.toFixed(4)}°, {watershed.outlet.lng.toFixed(4)}°</span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div className="bg-indigo-950/30 p-2.5 rounded-lg border border-indigo-500/30">
              <div className="text-[10px] text-slate-400 mb-0.5">CATCHMENT AREA</div>
              <span className="text-sm font-bold text-indigo-400">{watershed.catchment_area_km2} km²</span>
            </div>
            <div className="bg-[#0a0d14]/90 p-2.5 rounded-lg border border-[#1f293d]">
              <div className="text-[10px] text-slate-400 mb-0.5">AREA (m²)</div>
              <span className="text-xs font-semibold text-slate-200">{watershed.catchment_area_m2.toLocaleString()}</span>
            </div>
            <div className="bg-[#0a0d14]/90 p-2.5 rounded-lg border border-[#1f293d]">
              <div className="flex items-center space-x-1 text-[10px] text-slate-400 mb-0.5">
                <Maximize2 className="w-3 h-3" />
                <span>PERIMETER</span>
              </div>
              <span className="text-xs font-semibold text-emerald-400">{watershed.perimeter_km} km</span>
            </div>
            <div className="bg-[#0a0d14]/90 p-2.5 rounded-lg border border-[#1f293d]">
              <div className="flex items-center space-x-1 text-[10px] text-slate-400 mb-0.5">
                <BarChart2 className="w-3 h-3" />
                <span>AVG SLOPE</span>
              </div>
              <span className="text-xs font-semibold text-amber-400">{watershed.avg_slope_deg}°</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
