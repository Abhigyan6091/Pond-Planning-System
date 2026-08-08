import React, { useState } from 'react';
import { CloudRain, TrendingUp, Calendar, Droplets, Info, ChevronDown, ChevronUp } from 'lucide-react';
import { RainfallData } from '../types/terrain';

interface RainfallPanelProps {
  rainfall: RainfallData | null;
  isLoading: boolean;
  onClose: () => void;
}

const MONTH_ABBR = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

const CLASS_COLOR: Record<string, string> = {
  'Arid': 'text-red-400',
  'Semi-Arid': 'text-orange-400',
  'Sub-Humid': 'text-yellow-400',
  'Humid': 'text-emerald-400',
  'Very Humid': 'text-cyan-400',
  'Unknown': 'text-slate-400',
};

export const RainfallPanel: React.FC<RainfallPanelProps> = ({ rainfall, isLoading, onClose }) => {
  const [showYearly, setShowYearly] = useState(false);

  if (isLoading) {
    return (
      <div className="absolute bottom-6 left-72 z-[900] w-80 bg-[#121824]/95 backdrop-blur-md border border-[#1f293d] rounded-xl p-4 shadow-2xl">
        <div className="flex items-center space-x-3">
          <div className="w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-slate-300">Fetching rainfall from Open-Meteo...</span>
        </div>
      </div>
    );
  }

  if (!rainfall) return null;

  const maxMonthly = Math.max(...(rainfall.monthly_avg?.map(m => m.avg_mm) ?? [1]), 1);
  const classColor = CLASS_COLOR[rainfall.rainfall_class] || 'text-slate-400';

  return (
    <div className="absolute bottom-6 left-72 z-[900] w-84 bg-[#121824]/95 backdrop-blur-md border border-[#1f293d] rounded-xl shadow-2xl overflow-hidden" style={{ width: '320px' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#1f293d]">
        <div className="flex items-center space-x-2">
          <CloudRain className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-semibold text-slate-200">RAINFALL ANALYSIS</span>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-xs">✕</button>
      </div>

      <div className="p-3 space-y-3">
        {/* Source attribution */}
        <div className="text-[10px] font-mono text-slate-500 flex items-center space-x-1">
          <Info className="w-3 h-3" />
          <span>{rainfall.data_source} · {rainfall.start_year}–{rainfall.end_year}</span>
        </div>

        {!rainfall.success ? (
          <div className="text-xs text-amber-400 bg-amber-900/20 border border-amber-700/30 rounded-lg p-2">
            ⚠ {rainfall.message}
          </div>
        ) : (
          <>
            {/* Climate class badge */}
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider">Climate Class</span>
              <span className={`text-xs font-bold font-mono ${classColor}`}>{rainfall.rainfall_class}</span>
            </div>

            {/* Key stats grid */}
            <div className="grid grid-cols-2 gap-1.5 text-xs font-mono">
              {[
                { label: 'Annual Avg', value: `${rainfall.annual_avg_mm} mm`, icon: <TrendingUp className="w-3 h-3 text-cyan-400" /> },
                { label: 'Annual Max', value: `${rainfall.annual_max_mm} mm`, icon: <TrendingUp className="w-3 h-3 text-emerald-400" /> },
                { label: 'Monsoon (Jun–Sep)', value: `${rainfall.monsoon_avg_mm} mm`, icon: <CloudRain className="w-3 h-3 text-blue-400" /> },
                { label: 'Monsoon %', value: `${(rainfall.monsoon_fraction * 100).toFixed(0)}%`, icon: <Droplets className="w-3 h-3 text-indigo-400" /> },
              ].map(({ label, value, icon }) => (
                <div key={label} className="bg-[#0a0d14]/80 border border-[#1f293d] rounded-lg p-2">
                  <div className="flex items-center space-x-1 text-[10px] text-slate-400 mb-0.5">
                    {icon}<span>{label}</span>
                  </div>
                  <span className="font-semibold text-slate-100">{value}</span>
                </div>
              ))}
            </div>

            {/* Monthly bar chart */}
            {rainfall.monthly_avg && rainfall.monthly_avg.length === 12 && (
              <div>
                <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-1.5 flex items-center space-x-1">
                  <Calendar className="w-3 h-3" /><span>Monthly Average (mm)</span>
                </div>
                <div className="flex items-end gap-[3px] h-16 px-0.5">
                  {rainfall.monthly_avg.map((m) => {
                    const pct = (m.avg_mm / maxMonthly) * 100;
                    const isMonsoon = m.month >= 6 && m.month <= 9;
                    return (
                      <div key={m.month} className="flex-1 flex flex-col items-center gap-0.5" title={`${m.month_name}: ${m.avg_mm} mm`}>
                        <div className="w-full rounded-t-sm transition-all" style={{
                          height: `${Math.max(2, pct * 0.56)}px`,
                          background: isMonsoon
                            ? 'linear-gradient(to top, #1d4ed8, #60a5fa)'
                            : 'linear-gradient(to top, #1e3a5f, #3b82f6)',
                        }} />
                        <span className="text-[8px] text-slate-500">{MONTH_ABBR[m.month - 1]}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="text-[9px] text-slate-500 mt-0.5">
                  <span className="inline-block w-2 h-2 rounded-sm bg-blue-400 mr-1 align-middle" />Monsoon months highlighted
                </div>
              </div>
            )}

            {/* Yearly totals toggle */}
            {rainfall.yearly_totals && rainfall.yearly_totals.length > 0 && (
              <div>
                <button
                  onClick={() => setShowYearly(!showYearly)}
                  className="w-full flex items-center justify-between text-[10px] text-slate-400 hover:text-slate-200 py-1 transition-all"
                >
                  <span>Yearly totals ({rainfall.start_year}–{rainfall.end_year})</span>
                  {showYearly ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                </button>
                {showYearly && (
                  <div className="max-h-32 overflow-y-auto space-y-0.5 text-[10px] font-mono">
                    {rainfall.yearly_totals.map((y) => (
                      <div key={y.year} className="flex justify-between text-slate-300 px-1">
                        <span className="text-slate-500">{y.year}</span>
                        <span>{y.annual_total_mm.toFixed(0)} mm</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
