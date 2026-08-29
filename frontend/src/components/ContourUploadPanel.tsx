/**
 * ContourUploadPanel.tsx
 * ======================
 * Phase 2 — KML/KMZ upload panel.
 *
 * Shows a file picker and "Analyze" button. After a successful analysis,
 * displays the contour metadata, terrain stats, pond site, and catchment.
 *
 * This component is designed to be embedded in the Dashboard alongside
 * the existing map-based workflow — it does NOT replace any Phase 1 UI.
 */
import React, { useRef, useState } from 'react';
import {
  Upload, FileText, Mountain, Droplets, BarChart2, X, CheckCircle, AlertCircle, Loader,
} from 'lucide-react';
import { demService } from '../services/api';
import { ContourAnalysisResponse } from '../types/terrain';

interface ContourUploadPanelProps {
  onAnalysisComplete: (result: ContourAnalysisResponse) => void;
  onClose: () => void;
}

export const ContourUploadPanel: React.FC<ContourUploadPanelProps> = ({
  onAnalysisComplete,
  onClose,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<ContourAnalysisResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    setSelectedFile(f);
    setResult(null);
    setErrorMsg(null);
  };

  const handleAnalyze = async () => {
    if (!selectedFile) return;
    setIsAnalyzing(true);
    setErrorMsg(null);
    setResult(null);
    try {
      const res = await demService.analyzeContour(selectedFile);
      if (res.success) {
        setResult(res);
        onAnalysisComplete(res);
      } else {
        setErrorMsg(res.error_message || 'Analysis failed.');
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setErrorMsg(typeof detail === 'string' ? detail : 'Error communicating with server.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const tierColor = (tier: string) => {
    if (tier === 'Recommended') return 'text-emerald-400';
    if (tier === 'Highly Suitable') return 'text-cyan-400';
    if (tier === 'Moderately Suitable') return 'text-yellow-400';
    return 'text-rose-400';
  };

  return (
    <div className="w-full flex flex-col space-y-3">

      {/* ── File Picker ── */}
      <div
        className="relative border-2 border-dashed border-[#1f293d] hover:border-cyan-500/60 rounded-xl p-4 cursor-pointer transition-all group"
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".kml,.kmz"
          className="hidden"
          onChange={handleFileChange}
        />
        <div className="flex flex-col items-center space-y-2">
          <div className="w-10 h-10 rounded-lg bg-cyan-500/10 group-hover:bg-cyan-500/20 flex items-center justify-center transition-all">
            <Upload className="w-5 h-5 text-cyan-400" />
          </div>
          {selectedFile ? (
            <div className="text-center">
              <p className="text-xs font-mono text-cyan-300 font-semibold">{selectedFile.name}</p>
              <p className="text-[10px] text-slate-500">{(selectedFile.size / 1024).toFixed(0)} KB</p>
            </div>
          ) : (
            <div className="text-center">
              <p className="text-xs font-mono text-slate-300">Choose KML or KMZ file</p>
              <p className="text-[10px] text-slate-500">Contour map in KML 2.2 or KMZ format</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Analyze Button ── */}
      <button
        onClick={handleAnalyze}
        disabled={!selectedFile || isAnalyzing}
        className="w-full flex items-center justify-center space-x-2 py-2 rounded-lg
          bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500
          text-white text-xs font-semibold font-mono transition-all shadow-lg shadow-cyan-900/30
          disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {isAnalyzing ? (
          <>
            <Loader className="w-3.5 h-3.5 animate-spin" />
            <span>Analyzing terrain…</span>
          </>
        ) : (
          <>
            <BarChart2 className="w-3.5 h-3.5" />
            <span>Analyze Contour Map</span>
          </>
        )}
      </button>

      {/* ── Error ── */}
      {errorMsg && (
        <div className="flex items-start space-x-2 bg-rose-500/10 border border-rose-500/30 rounded-lg px-3 py-2">
          <AlertCircle className="w-3.5 h-3.5 text-rose-400 mt-0.5 shrink-0" />
          <p className="text-[10px] font-mono text-rose-300">{errorMsg}</p>
        </div>
      )}

      {/* ── Results ── */}
      {result && result.success && (
        <div className="flex flex-col space-y-2 text-[10px] font-mono">

          {/* Input summary */}
          {result.input && (
            <div className="bg-[#0d1520]/80 border border-[#1f293d] rounded-lg p-3 space-y-1">
              <div className="flex items-center space-x-1.5 mb-1.5">
                <FileText className="w-3 h-3 text-cyan-400" />
                <span className="text-slate-300 font-bold text-[10px] uppercase tracking-wide">Contour Input</span>
                <span className="ml-auto bg-cyan-500/20 text-cyan-400 px-1.5 py-0.5 rounded text-[9px] border border-cyan-500/30">
                  {result.input.format}
                </span>
              </div>
              <Row label="Contours" value={`${result.input.contour_count}`} />
              <Row label="Elev Range" value={`${result.input.elevation_min_m}m – ${result.input.elevation_max_m}m`} />
              <Row label="Interval" value={`${result.input.contour_interval_m.toFixed(1)} m`} />
            </div>
          )}

          {/* Terrain stats */}
          {result.terrain && (
            <div className="bg-[#0d1520]/80 border border-[#1f293d] rounded-lg p-3 space-y-1">
              <div className="flex items-center space-x-1.5 mb-1.5">
                <Mountain className="w-3 h-3 text-blue-400" />
                <span className="text-slate-300 font-bold text-[10px] uppercase tracking-wide">Reconstructed Terrain</span>
              </div>
              <Row label="Grid" value={`${result.terrain.grid_rows}×${result.terrain.grid_cols}`} />
              <Row label="Pixel Size" value={`${result.terrain.pixel_size_m.toFixed(1)} m`} />
              <Row label="Min Elev" value={`${result.terrain.min_elevation_m.toFixed(1)} m`} />
              <Row label="Max Elev" value={`${result.terrain.max_elevation_m.toFixed(1)} m`} />
              <Row label="Mean Elev" value={`${result.terrain.mean_elevation_m.toFixed(1)} m`} />
            </div>
          )}

          {/* Pond site */}
          {result.pond_site && (
            <div className="bg-[#0d1520]/80 border border-[#1f293d] rounded-lg p-3 space-y-1">
              <div className="flex items-center space-x-1.5 mb-1.5">
                <CheckCircle className="w-3 h-3 text-emerald-400" />
                <span className="text-slate-300 font-bold text-[10px] uppercase tracking-wide">Recommended Pond Site</span>
                <span className={`ml-auto text-[9px] font-bold ${tierColor(result.pond_site.suitability_tier)}`}>
                  {result.pond_site.suitability_tier}
                </span>
              </div>
              <Row label="Lat / Lon" value={`${result.pond_site.latitude.toFixed(5)}° N, ${result.pond_site.longitude.toFixed(5)}° E`} />
              <Row label="Elevation" value={`${result.pond_site.elevation_m.toFixed(1)} m`} />
              <Row label="Slope" value={`${result.pond_site.slope_deg.toFixed(1)}°`} />
              <Row label="Score" value={`${result.pond_site.suitability_score.toFixed(1)} / 100`} />
              <p className="text-slate-400 text-[9px] mt-1 leading-relaxed">{result.pond_site.reason}</p>
            </div>
          )}

          {/* Catchment */}
          {result.catchment && (
            <div className="bg-[#0d1520]/80 border border-[#1f293d] rounded-lg p-3 space-y-1">
              <div className="flex items-center space-x-1.5 mb-1.5">
                <Droplets className="w-3 h-3 text-blue-400" />
                <span className="text-slate-300 font-bold text-[10px] uppercase tracking-wide">Catchment</span>
              </div>
              <Row label="Area" value={`${result.catchment.area_km2.toFixed(4)} km²`} />
              <Row label="Area (m²)" value={`${result.catchment.area_m2.toFixed(0)}`} />
              <Row label="Perimeter" value={`${result.catchment.perimeter_km.toFixed(2)} km`} />
              <Row label="Avg Slope" value={`${result.catchment.avg_slope_deg.toFixed(1)}°`} />
              <Row label="Contributing Cells" value={`${result.catchment.contributing_cells}`} />
            </div>
          )}

        </div>
      )}
    </div>
  );
};

/** Compact label / value row */
const Row: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex justify-between items-baseline">
    <span className="text-slate-500">{label}</span>
    <span className="text-slate-200 font-semibold">{value}</span>
  </div>
);
