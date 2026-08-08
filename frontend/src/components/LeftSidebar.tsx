import React from 'react';
import {
  Layers, Eye, EyeOff, Mountain, Waves, Compass, Activity,
  ShieldAlert, GitBranch, Grid, Download, Star, MapPin,
} from 'lucide-react';
import { LayerVisibility, ContourPolylineData, WatershedData } from '../types/terrain';
import { demService } from '../services/api';

interface LeftSidebarProps {
  layers: LayerVisibility;
  onToggleLayer: (layerKey: keyof LayerVisibility) => void;
  demLoaded: boolean;
  demId?: string;
  contours?: ContourPolylineData[];
  watershed?: WatershedData | null;
}

export const LeftSidebar: React.FC<LeftSidebarProps> = ({
  layers, onToggleLayer, demLoaded, demId, contours, watershed,
}) => {
  const layerItems: {
    key: keyof LayerVisibility; label: string;
    icon: React.ReactNode; color: string; requiresDem?: boolean;
  }[] = [
    { key: 'demOverlay',     label: 'DEM Color Overlay',      icon: <Grid className="w-4 h-4" />,        color: 'text-cyan-400',    requiresDem: true },
    { key: 'hillshade',      label: 'Hillshade Shading',      icon: <Mountain className="w-4 h-4" />,    color: 'text-amber-400',   requiresDem: true },
    { key: 'contours',       label: 'Contour Lines',          icon: <Activity className="w-4 h-4" />,    color: 'text-emerald-400', requiresDem: true },
    { key: 'slopeHeatmap',   label: 'Slope Heatmap',          icon: <ShieldAlert className="w-4 h-4" />, color: 'text-rose-400',    requiresDem: true },
    { key: 'watershed',      label: 'Watershed Catchment',    icon: <Waves className="w-4 h-4" />,       color: 'text-indigo-400' },
    { key: 'flowVectors',    label: 'Flow Direction Vectors', icon: <Compass className="w-4 h-4" />,     color: 'text-orange-400',  requiresDem: true },
    { key: 'streamNetwork',  label: 'Stream Networks',        icon: <GitBranch className="w-4 h-4" />,   color: 'text-blue-400',    requiresDem: true },
    { key: 'candidateSites', label: 'Candidate Pond Sites',   icon: <MapPin className="w-4 h-4" />,      color: 'text-lime-400' },
    { key: 'recommendedSite',label: 'Recommended Site',       icon: <Star className="w-4 h-4" />,        color: 'text-amber-400' },
  ];

  return (
    <aside className="absolute top-20 left-4 z-[900] w-64 bg-[#121824]/90 backdrop-blur-md border border-[#1f293d] rounded-xl p-3 shadow-2xl transition-all space-y-3">
      <div className="flex items-center justify-between pb-2 border-b border-[#1f293d]">
        <div className="flex items-center space-x-2 text-xs font-semibold text-slate-200">
          <Layers className="w-4 h-4 text-blue-400" />
          <span>GIS MAP LAYERS</span>
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-medium ${
          demLoaded ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-500'
        }`}>
          {demLoaded ? 'DEM ACTIVE' : 'NO DEM'}
        </span>
      </div>

      <div className="space-y-1">
        {layerItems.map((item) => {
          const isVisible = layers[item.key];
          const disabled = item.requiresDem && !demLoaded;
          return (
            <button
              key={item.key}
              onClick={() => !disabled && onToggleLayer(item.key)}
              disabled={disabled}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-all ${
                disabled
                  ? 'opacity-30 cursor-not-allowed text-slate-500'
                  : isVisible
                  ? 'bg-[#1a2332] text-slate-100 font-medium border border-[#2a364f]'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#161d2b]'
              }`}
            >
              <div className="flex items-center space-x-2.5">
                <span className={disabled ? 'text-slate-600' : item.color}>{item.icon}</span>
                <span>{item.label}</span>
              </div>
              {!disabled && (
                isVisible
                  ? <Eye className="w-3.5 h-3.5 text-cyan-400" />
                  : <EyeOff className="w-3.5 h-3.5 text-slate-600" />
              )}
            </button>
          );
        })}
      </div>

      {/* Export Section */}
      {demLoaded && (
        <div className="pt-2 border-t border-[#1f293d] space-y-1.5">
          <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider px-1">EXPORT DATA</div>
          <div className="grid grid-cols-2 gap-1.5">
            {contours && contours.length > 0 && demId && (
              <>
                <button
                  onClick={() => demService.exportContoursGeoJSON(demId!, contours!)}
                  className="flex items-center justify-center space-x-1 bg-[#1a2332] hover:bg-emerald-950/40 text-emerald-400 border border-emerald-500/30 py-1.5 rounded-lg text-[11px] font-mono font-medium transition-all"
                >
                  <Download className="w-3 h-3" /><span>Contours GeoJSON</span>
                </button>
                <button
                  onClick={() => demService.exportContoursCSV(demId!, contours!)}
                  className="flex items-center justify-center space-x-1 bg-[#1a2332] hover:bg-cyan-950/40 text-cyan-400 border border-cyan-500/30 py-1.5 rounded-lg text-[11px] font-mono font-medium transition-all"
                >
                  <Download className="w-3 h-3" /><span>Contours CSV</span>
                </button>
              </>
            )}
            {watershed && (
              <button
                onClick={() => demService.exportCatchmentGeoJSON(watershed.catchment_polygon, {
                  catchment_area_km2: watershed.catchment_area_km2,
                  perimeter_km: watershed.perimeter_km,
                  avg_slope_deg: watershed.avg_slope_deg,
                })}
                className="col-span-2 flex items-center justify-center space-x-1 bg-[#1a2332] hover:bg-indigo-950/40 text-indigo-400 border border-indigo-500/30 py-1.5 rounded-lg text-[11px] font-mono font-medium transition-all"
              >
                <Download className="w-3 h-3" /><span>Catchment GeoJSON</span>
              </button>
            )}
          </div>
        </div>
      )}
    </aside>
  );
};
