import React, { useState } from 'react';
import Plot from 'react-plotly.js';
import { Terrain3DData } from '../types/terrain';
import { X, Box, Eye, Layers } from 'lucide-react';

interface Terrain3DModalProps {
  data3D: Terrain3DData;
  onClose: () => void;
}

export const Terrain3DModal: React.FC<Terrain3DModalProps> = ({ data3D, onClose }) => {
  const [colorscale, setColorscale] = useState<string>('Earth');

  const plotData: any = [
    {
      z: data3D.z,
      x: data3D.x,
      y: data3D.y,
      type: 'surface',
      colorscale: colorscale,
      contours: {
        z: { show: true, usecolormap: true, highlightcolor: '#4299e1', project: { z: true } },
      },
      lighting: { ambient: 0.65, diffuse: 0.8, roughness: 0.5, specular: 0.2 },
    },
  ];

  const plotLayout: any = {
    autosize: true,
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    margin: { l: 0, r: 0, t: 0, b: 0 },
    scene: {
      xaxis: { title: { text: 'Longitude', font: { color: '#94a3b8' } }, tickfont: { color: '#64748b' }, gridcolor: '#1e293b' },
      yaxis: { title: { text: 'Latitude', font: { color: '#94a3b8' } }, tickfont: { color: '#64748b' }, gridcolor: '#1e293b' },
      zaxis: { title: { text: 'Elevation (m)', font: { color: '#94a3b8' } }, tickfont: { color: '#64748b' }, gridcolor: '#1e293b' },
      camera: { eye: { x: 1.4, y: -1.4, z: 1.1 } },
      aspectratio: { x: 1, y: 1, z: 0.4 },
    },
  };

  return (
    <div className="fixed inset-0 z-[1100] flex items-center justify-center bg-black/80 backdrop-blur-md p-4">
      <div className="bg-[#121824] border border-[#1f293d] rounded-2xl w-full max-w-5xl h-[85vh] p-5 shadow-2xl flex flex-col space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1f293d] pb-3 shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-purple-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-purple-500/20">
              <Box className="w-4 h-4 text-white" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100">3D TERRAIN SURFACE ENGINE</h2>
              <p className="text-[11px] font-mono text-purple-400">
                Interactive Mesh ({data3D.z.length} × {data3D.z[0]?.length}) · Elevation Range: {data3D.min_z.toFixed(0)}m – {data3D.max_z.toFixed(0)}m
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {/* Color scale picker */}
            <div className="flex items-center space-x-1.5 bg-[#0a0d14] border border-[#1f293d] px-2.5 py-1 rounded-lg text-xs font-mono">
              <Layers className="w-3.5 h-3.5 text-purple-400" />
              <span className="text-slate-400 text-[10px]">PALETTE:</span>
              <select
                value={colorscale}
                onChange={(e) => setColorscale(e.target.value)}
                className="bg-transparent text-slate-200 text-xs outline-none cursor-pointer"
              >
                <option value="Earth">Earth</option>
                <option value="Viridis">Viridis</option>
                <option value="Portland">Portland</option>
                <option value="Jet">Jet</option>
                <option value="Hot">Hot</option>
                <option value="Greys">Greys</option>
              </select>
            </div>

            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* 3D Plot Container */}
        <div className="flex-1 w-full rounded-xl overflow-hidden bg-[#0a0d14] border border-[#1f293d] relative">
          <Plot
            data={plotData}
            layout={plotLayout}
            config={{ responsive: true, displayModeBar: true, displaylogo: false }}
            style={{ width: '100%', height: '100%' }}
          />

          <div className="absolute bottom-3 left-3 pointer-events-none bg-black/60 backdrop-blur-sm border border-slate-700/50 text-[10px] font-mono text-slate-300 px-3 py-1.5 rounded-full flex items-center space-x-1.5">
            <Eye className="w-3 h-3 text-purple-400" />
            <span>Click & Drag to rotate 3D view · Scroll to zoom</span>
          </div>
        </div>
      </div>
    </div>
  );
};
