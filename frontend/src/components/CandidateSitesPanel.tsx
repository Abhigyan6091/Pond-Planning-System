import React, { useState } from 'react';
import { List, ChevronDown, ChevronUp, Star, Download } from 'lucide-react';
import { CandidateSite } from '../types/terrain';
import { demService } from '../services/api';

interface CandidateSitesPanelProps {
  candidates: CandidateSite[];
  selectedSite: CandidateSite | null;
  onSelectSite: (site: CandidateSite) => void;
  isLoading: boolean;
  onClose: () => void;
}

const TIER_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  'Recommended':        { bg: 'bg-amber-500/15 border-amber-500/30',   text: 'text-amber-400',  dot: 'bg-amber-400' },
  'Highly Suitable':    { bg: 'bg-emerald-500/15 border-emerald-500/30', text: 'text-emerald-400', dot: 'bg-emerald-400' },
  'Moderately Suitable':{ bg: 'bg-blue-500/15 border-blue-500/30',      text: 'text-blue-400',   dot: 'bg-blue-400' },
  'Poor':               { bg: 'bg-slate-700/30 border-slate-600/30',    text: 'text-slate-400',  dot: 'bg-slate-500' },
};

export const CandidateSitesPanel: React.FC<CandidateSitesPanelProps> = ({
  candidates, selectedSite, onSelectSite, isLoading, onClose,
}) => {
  const [collapsed, setCollapsed] = useState(false);

  const handleExport = () => {
    if (candidates.length > 0) demService.exportCandidatesCSV(candidates);
  };

  const handleExportGeoJSON = () => {
    if (candidates.length > 0) demService.exportPondSitesGeoJSON(candidates);
  };

  return (
    <div
      className="absolute z-[900] bg-[#121824]/95 backdrop-blur-md border border-[#1f293d] rounded-xl shadow-2xl overflow-hidden"
      style={{ bottom: '1.5rem', left: '17rem', width: '280px' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-[#1f293d]">
        <div className="flex items-center space-x-2">
          <List className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-semibold text-slate-200">CANDIDATE SITES</span>
          {candidates.length > 0 && (
            <span className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-mono px-1.5 py-0.5 rounded-full">
              {candidates.length}
            </span>
          )}
        </div>
        <div className="flex items-center space-x-1">
          {candidates.length > 0 && (
            <>
              <button onClick={handleExport} title="Export CSV" className="p-1 text-slate-400 hover:text-cyan-400">
                <Download className="w-3.5 h-3.5" />
              </button>
            </>
          )}
          <button onClick={() => setCollapsed(!collapsed)} className="text-slate-400 hover:text-slate-200 p-1">
            {collapsed ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-xs p-1">✕</button>
        </div>
      </div>

      {!collapsed && (
        <div>
          {isLoading ? (
            <div className="flex items-center space-x-3 p-4">
              <div className="w-4 h-4 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
              <span className="text-xs text-slate-400">Analyzing terrain...</span>
            </div>
          ) : candidates.length === 0 ? (
            <div className="p-4 text-xs text-slate-500 text-center">
              No candidates yet. Analyze a village to identify pond sites.
            </div>
          ) : (
            <div className="max-h-72 overflow-y-auto divide-y divide-[#1a2332]">
              {candidates.map((site) => {
                const style = TIER_STYLES[site.suitability_tier] || TIER_STYLES['Poor'];
                const isSelected = selectedSite?.site_id === site.site_id;
                const isRec = site.rank === 1;
                return (
                  <button
                    key={site.site_id}
                    onClick={() => onSelectSite(site)}
                    className={`w-full text-left px-3 py-2.5 transition-all hover:bg-[#1a2332] ${isSelected ? 'bg-[#1a2332] border-l-2 border-cyan-400' : ''}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center space-x-2">
                        {isRec && <Star className="w-3 h-3 text-amber-400 fill-amber-400" />}
                        <span className={`text-[10px] font-bold ${style.text}`}>#{site.rank}</span>
                        <span className={`inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-full border font-mono ${style.bg} ${style.text}`}>
                          <div className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
                          {site.suitability_tier}
                        </span>
                      </div>
                      <span className={`text-xs font-bold font-mono ${style.text}`}>
                        {site.scores.composite_score.toFixed(0)}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-x-2 text-[9px] font-mono text-slate-400">
                      <span>⛰ {site.elevation_m}m</span>
                      <span>↗ {site.slope_deg}°</span>
                      <span>💧 {site.catchment_area_km2.toFixed(2)}km²</span>
                      <span>depth {site.estimated_depth_m}m</span>
                      <span>{(site.estimated_volume_m3 / 1000).toFixed(1)}k m³</span>
                      {site.estimated_runoff_m3 && (
                        <span>Q {(site.estimated_runoff_m3 / 1000).toFixed(0)}k m³</span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {/* Export buttons */}
          {candidates.length > 0 && (
            <div className="px-3 py-2 border-t border-[#1f293d] flex gap-2">
              <button
                onClick={handleExport}
                className="flex-1 text-[10px] font-mono text-cyan-400 border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 py-1.5 rounded-lg flex items-center justify-center gap-1 transition-all"
              >
                <Download className="w-3 h-3" /> CSV
              </button>
              <button
                onClick={handleExportGeoJSON}
                className="flex-1 text-[10px] font-mono text-emerald-400 border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 py-1.5 rounded-lg flex items-center justify-center gap-1 transition-all"
              >
                <Download className="w-3 h-3" /> GeoJSON
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
