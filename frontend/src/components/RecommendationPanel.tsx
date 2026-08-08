import React, { useState } from 'react';
import { Star, MapPin, ChevronDown, ChevronUp, CheckCircle, AlertTriangle, Target, Waves, Mountain, Droplets, BarChart2 } from 'lucide-react';
import { CandidateSite } from '../types/terrain';

interface RecommendationPanelProps {
  recommended: CandidateSite | null;
  onClose: () => void;
  onSelectOnMap: (site: CandidateSite) => void;
}

const SCORE_COLORS = (v: number) => v >= 0.7 ? 'text-emerald-400' : v >= 0.45 ? 'text-yellow-400' : 'text-rose-400';
const BAR_COLOR = (v: number) => v >= 0.7 ? '#10b981' : v >= 0.45 ? '#f59e0b' : '#f43f5e';

const ScoreBar: React.FC<{ label: string; value: number; tooltip: string }> = ({ label, value, tooltip }) => (
  <div className="flex items-center gap-2" title={tooltip}>
    <span className="text-[10px] text-slate-400 w-24 shrink-0">{label}</span>
    <div className="flex-1 bg-[#0a0d14] rounded-full h-1.5 overflow-hidden">
      <div className="h-full rounded-full transition-all" style={{ width: `${(value * 100).toFixed(0)}%`, background: BAR_COLOR(value) }} />
    </div>
    <span className={`text-[10px] font-mono font-bold w-8 text-right ${SCORE_COLORS(value)}`}>
      {(value * 100).toFixed(0)}%
    </span>
  </div>
);

export const RecommendationPanel: React.FC<RecommendationPanelProps> = ({
  recommended, onClose, onSelectOnMap,
}) => {
  const [expanded, setExpanded] = useState(true);

  if (!recommended) return null;

  const score = recommended.scores.composite_score;
  const scoreColor = score >= 70 ? '#f59e0b' : score >= 50 ? '#10b981' : score >= 35 ? '#3b82f6' : '#6b7280';

  return (
    <div className="absolute top-20 right-4 z-[900] w-80 bg-[#121824]/96 backdrop-blur-md border border-amber-500/30 rounded-xl shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-amber-900/40 to-[#121824]/60 border-b border-amber-500/20">
        <div className="flex items-center space-x-2">
          <Star className="w-4 h-4 text-amber-400 fill-amber-400" />
          <span className="text-xs font-bold text-amber-300 tracking-wide">RECOMMENDED SITE</span>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-slate-400 hover:text-slate-200"
          >
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-xs">✕</button>
        </div>
      </div>

      {expanded && (
        <div className="p-3 space-y-3">
          {/* Score ring + location */}
          <div className="flex items-center gap-3">
            <div className="relative w-16 h-16 shrink-0">
              <svg viewBox="0 0 36 36" className="w-16 h-16 -rotate-90">
                <circle cx="18" cy="18" r="15.9" fill="none" stroke="#1f293d" strokeWidth="3" />
                <circle
                  cx="18" cy="18" r="15.9" fill="none"
                  stroke={scoreColor} strokeWidth="3"
                  strokeDasharray={`${score} ${100 - score}`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-sm font-bold" style={{ color: scoreColor }}>{score.toFixed(0)}</span>
                <span className="text-[8px] text-slate-500">/100</span>
              </div>
            </div>

            <div className="min-w-0">
              <div className="text-[10px] font-mono text-slate-400 mb-1 flex items-center space-x-1">
                <MapPin className="w-3 h-3 text-amber-400" />
                <span>{recommended.lat.toFixed(5)}°N, {recommended.lng.toFixed(5)}°E</span>
              </div>
              <div className="grid grid-cols-2 gap-1 text-[10px] font-mono">
                <span className="text-slate-400">Elevation</span>
                <span className="text-slate-200">{recommended.elevation_m} m</span>
                <span className="text-slate-400">Slope</span>
                <span className="text-slate-200">{recommended.slope_deg}°</span>
                <span className="text-slate-400">Catchment</span>
                <span className="text-slate-200">{recommended.catchment_area_km2.toFixed(3)} km²</span>
              </div>
            </div>
          </div>

          {/* Pond estimates */}
          <div className="bg-[#0a0d14]/80 rounded-lg border border-[#1f293d] p-2.5 grid grid-cols-3 gap-2 text-center">
            {[
              { label: 'Depth', value: `${recommended.estimated_depth_m} m`, Icon: Mountain, color: 'text-cyan-400' },
              { label: 'Surface', value: `${(recommended.estimated_surface_area_m2 / 10000).toFixed(2)} ha`, Icon: Waves, color: 'text-blue-400' },
              { label: 'Volume', value: recommended.estimated_volume_m3 > 1000
                ? `${(recommended.estimated_volume_m3/1000).toFixed(1)}k m³`
                : `${recommended.estimated_volume_m3.toFixed(0)} m³`,
                Icon: Droplets, color: 'text-indigo-400' },
            ].map(({ label, value, Icon, color }) => (
              <div key={label}>
                <Icon className={`w-3.5 h-3.5 ${color} mx-auto mb-0.5`} />
                <div className="text-[10px] text-slate-400">{label}</div>
                <div className="text-xs font-bold text-slate-100 font-mono">{value}</div>
              </div>
            ))}
          </div>

          {/* Runoff estimate */}
          {recommended.estimated_runoff_m3 && (
            <div className="bg-blue-900/10 border border-blue-500/20 rounded-lg px-3 py-2 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Droplets className="w-3.5 h-3.5 text-blue-400" />
                <div>
                  <div className="text-[10px] text-slate-400">Est. Annual Runoff</div>
                  <div className="text-xs font-bold text-blue-300 font-mono">
                    {recommended.estimated_runoff_m3.toLocaleString()} m³
                  </div>
                </div>
              </div>
              <div className="text-[9px] text-slate-500 text-right">
                C = {recommended.runoff_coefficient}
              </div>
            </div>
          )}

          {/* Score breakdown */}
          <div>
            <div className="flex items-center space-x-1 text-[10px] text-slate-400 uppercase tracking-wider mb-2">
              <BarChart2 className="w-3 h-3" /><span>Score Breakdown</span>
            </div>
            <div className="space-y-1.5">
              <ScoreBar label="Slope" value={recommended.scores.slope_score} tooltip="Flatter terrain → higher score" />
              <ScoreBar label="Depression" value={recommended.scores.depression_score} tooltip="Deeper natural sink → higher score" />
              <ScoreBar label="Catchment" value={recommended.scores.catchment_score} tooltip="More upstream area → higher score" />
              <ScoreBar label="Elevation" value={recommended.scores.elevation_score} tooltip="Lower within ROI → higher score" />
              <ScoreBar label="Rainfall" value={recommended.scores.rainfall_score} tooltip="More rainfall → higher score" />
            </div>
          </div>

          {/* Reasons */}
          {recommended.suitability_reasons.length > 0 && (
            <div>
              <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-1.5">WHY THIS SITE?</div>
              <div className="space-y-1">
                {recommended.suitability_reasons.map((r, i) => (
                  <div key={i} className={`flex items-start space-x-1.5 text-[11px] ${r.startsWith('✓') ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {r.startsWith('✓')
                      ? <CheckCircle className="w-3 h-3 mt-0.5 shrink-0" />
                      : <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />}
                    <span>{r.replace(/^[✓⚠]\s*/, '')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Navigate button */}
          <button
            onClick={() => onSelectOnMap(recommended)}
            className="w-full flex items-center justify-center space-x-2 bg-gradient-to-r from-amber-600 to-orange-500 hover:from-amber-500 hover:to-orange-400 text-white text-xs font-semibold py-2 rounded-lg transition-all shadow-lg shadow-amber-500/20"
          >
            <Target className="w-3.5 h-3.5" />
            <span>Focus on Map</span>
          </button>

          <p className="text-[9px] text-slate-500 leading-relaxed">
            ⚠ Planning estimate only. Field survey required before construction.
          </p>
        </div>
      )}
    </div>
  );
};
