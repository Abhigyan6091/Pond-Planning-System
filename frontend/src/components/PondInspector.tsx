import React from 'react';
import Plot from 'react-plotly.js';
import { PondInfo } from '../types/terrain';
import { Database, Waves, Layers, Maximize2, ArrowDownCircle, ArrowUpCircle } from 'lucide-react';
import { DraggablePanel } from './DraggablePanel';

interface PondInspectorProps {
  pond: PondInfo;
  onClose: () => void;
}

export const PondInspector: React.FC<PondInspectorProps> = ({ pond, onClose }) => {
  return (
    <DraggablePanel
      id="pond-inspector"
      title="POND ANALYSIS"
      subtitle={`Depth: ${pond.max_depth} m · Vol: ${pond.volume_m3.toLocaleString()} m³`}
      icon={<Database className="w-4 h-4 text-blue-400" />}
      initialPosition={{ top: 80, right: 380 }}
      width="340px"
      onClose={onClose}
      zIndex={950}
    >
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
            <span>CATCHMENT CELLS</span>
          </div>
          <span className="text-xs font-semibold text-indigo-300">{pond.catchment_cells}</span>
        </div>
      </div>

      {/* Elevation Details */}
      <div className="bg-[#0a0d14]/80 p-2.5 rounded-lg border border-[#1f293d] space-y-1.5 text-xs font-mono">
        <div className="flex items-center justify-between text-slate-300">
          <div className="flex items-center space-x-1.5">
            <ArrowDownCircle className="w-3.5 h-3.5 text-rose-400" />
            <span>Bottom Elevation:</span>
          </div>
          <span className="font-bold text-rose-300">{pond.bottom_elevation} m</span>
        </div>
        <div className="flex items-center justify-between text-slate-300">
          <div className="flex items-center space-x-1.5">
            <ArrowUpCircle className="w-3.5 h-3.5 text-cyan-400" />
            <span>Spill Water Level:</span>
          </div>
          <span className="font-bold text-cyan-300">{pond.water_level} m</span>
        </div>
      </div>

      {/* Stage-Storage Curve */}
      {pond.stage_storage_curve && pond.stage_storage_curve.length > 0 && (
        <div className="space-y-1.5 border-t border-[#1f293d] pt-2.5">
          <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center space-x-1">
            <Waves className="w-3 h-3 text-cyan-400" />
            <span>Stage-Storage Capacity Curve</span>
          </div>

          <div className="bg-[#0a0d14] rounded-lg p-1 border border-[#1f293d]">
            <Plot
              data={[
                {
                  x: pond.stage_storage_curve.map((pt) => pt.depth_m),
                  y: pond.stage_storage_curve.map((pt) => pt.volume_m3),
                  type: 'scatter',
                  mode: 'lines+markers',
                  name: 'Volume (m³)',
                  line: { color: '#38bdf8', width: 2.5 },
                  marker: { size: 4, color: '#0284c7' },
                },
              ]}
              layout={{
                width: 290,
                height: 150,
                margin: { l: 45, r: 10, t: 10, b: 30 },
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                xaxis: {
                  title: { text: 'Depth (m)', font: { size: 9, color: '#94a3b8' } },
                  tickfont: { size: 8, color: '#64748b' },
                  gridcolor: '#1e293b',
                },
                yaxis: {
                  title: { text: 'Storage (m³)', font: { size: 9, color: '#94a3b8' } },
                  tickfont: { size: 8, color: '#64748b' },
                  gridcolor: '#1e293b',
                },
                showlegend: false,
              }}
              config={{ displayModeBar: false, responsive: true }}
            />
          </div>
        </div>
      )}
    </DraggablePanel>
  );
};
