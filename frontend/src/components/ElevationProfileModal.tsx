import React from 'react';
import Plot from 'react-plotly.js';
import { ElevationProfileResponseData } from '../types/terrain';
import { X, TrendingUp, ArrowUpRight, ArrowDownRight, Download } from 'lucide-react';
import { demService } from '../services/api';

interface ElevationProfileModalProps {
  profileData: ElevationProfileResponseData;
  onClose: () => void;
}

export const ElevationProfileModal: React.FC<ElevationProfileModalProps> = ({ profileData, onClose }) => {
  const distances = profileData.profile.map((p) => p.distance_m);
  const elevations = profileData.profile.map((p) => p.elevation);

  const plotData: any = [
    {
      x: distances,
      y: elevations,
      type: 'scatter',
      mode: 'lines',
      fill: 'tozeroy',
      fillcolor: 'rgba(16, 185, 129, 0.15)',
      line: { color: '#10b981', width: 2.5 },
      name: 'Elevation',
      hovertemplate: 'Distance: %{x:.1f} m<br>Elevation: %{y:.1f} m<extra></extra>',
    },
  ];

  const plotLayout: any = {
    autosize: true,
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    margin: { l: 50, r: 20, t: 20, b: 40 },
    xaxis: {
      title: { text: 'Distance (m)', font: { color: '#94a3b8', size: 11 } },
      tickfont: { color: '#64748b', size: 10 },
      gridcolor: '#1e293b',
      zerolinecolor: '#1e293b',
    },
    yaxis: {
      title: { text: 'Elevation (m)', font: { color: '#94a3b8', size: 11 } },
      tickfont: { color: '#64748b', size: 10 },
      gridcolor: '#1e293b',
      zerolinecolor: '#1e293b',
    },
    hoverlabel: {
      bgcolor: '#121824',
      bordercolor: '#334155',
      font: { color: '#f8fafc', family: 'monospace', size: 11 },
    },
  };

  const handleExportCSV = () => {
    demService.exportProfileCSV(profileData.profile);
  };

  return (
    <div className="fixed inset-0 z-[1100] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-[#121824] border border-[#1f293d] rounded-2xl w-full max-w-4xl p-5 shadow-2xl space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1f293d] pb-3">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100">ELEVATION PROFILE</h2>
              <p className="text-[11px] font-mono text-slate-400">Interactive Line Transect Sample</p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleExportCSV}
              className="flex items-center space-x-1.5 bg-emerald-600/80 hover:bg-emerald-500 text-white font-medium text-xs px-3 py-1.5 rounded-lg transition-colors border border-emerald-500/40"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export CSV</span>
            </button>

            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Quick Stats Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
          <div className="bg-[#0a0d14]/90 p-2.5 rounded-xl border border-[#1f293d]">
            <div className="text-[10px] text-slate-400 mb-0.5">TRANSECT LENGTH</div>
            <div className="text-sm font-bold text-slate-200">{(profileData.total_distance_m / 1000).toFixed(2)} km</div>
          </div>
          <div className="bg-[#0a0d14]/90 p-2.5 rounded-xl border border-[#1f293d]">
            <div className="text-[10px] text-slate-400 mb-0.5">MIN / MAX ELEV</div>
            <div className="text-sm font-bold text-cyan-400">{profileData.min_elevation}m / {profileData.max_elevation}m</div>
          </div>
          <div className="bg-emerald-950/30 p-2.5 rounded-xl border border-emerald-500/30">
            <div className="flex items-center space-x-1 text-[10px] text-slate-400 mb-0.5">
              <ArrowUpRight className="w-3 h-3 text-emerald-400" />
              <span>ELEV GAIN</span>
            </div>
            <div className="text-sm font-bold text-emerald-400">+{profileData.elevation_gain_m} m</div>
          </div>
          <div className="bg-rose-950/30 p-2.5 rounded-xl border border-rose-500/30">
            <div className="flex items-center space-x-1 text-[10px] text-slate-400 mb-0.5">
              <ArrowDownRight className="w-3 h-3 text-rose-400" />
              <span>ELEV LOSS</span>
            </div>
            <div className="text-sm font-bold text-rose-400">-{profileData.elevation_loss_m} m</div>
          </div>
        </div>

        {/* Plotly Chart */}
        <div className="w-full h-80 rounded-xl overflow-hidden bg-[#0a0d14] border border-[#1f293d]">
          <Plot
            data={plotData}
            layout={plotLayout}
            config={{ responsive: true, displayModeBar: false }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>
      </div>
    </div>
  );
};
