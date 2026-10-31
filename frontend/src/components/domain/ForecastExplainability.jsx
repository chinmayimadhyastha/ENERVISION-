import React, { useEffect, useState } from 'react'
import {
  Sparkles,
  TrendingUp,
  TrendingDown,
  Info,
  Calendar,
  Layers,
  ChevronDown,
  ChevronUp,
  Cpu,
  CheckCircle2,
  AlertCircle,
  Zap,
  ArrowRight
} from 'lucide-react'
import { getForecastExplanation } from '../../services/api.js'
import { useLanguage } from '../../context/LanguageContext.jsx'
import Card from '../ui/Card.jsx'
import Badge from '../ui/Badge.jsx'
import LoadingState from '../ui/LoadingState.jsx'

export default function ForecastExplainability({ plantId, plantName, renewableType, model }) {
  const { language } = useLanguage()
  const isKn = language === 'kn'

  const [active, setActive] = useState(false)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showTemporal, setShowTemporal] = useState(false)

  const isRf = model === 'rf' || model === 'random_forest'

  useEffect(() => {
    // If not active, or invalid plant, don't fetch
    if (!active || !plantId || isRf) {
      if (isRf) setData(null)
      return
    }

    let isMounted = true
    setLoading(true)
    setError(null)

    getForecastExplanation({ plantId, model: 'auto' })
      .then((res) => {
        if (isMounted) {
          setData(res)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err?.userMessage || err?.message || 'Failed to compute SHAP explanations')
          setLoading(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [plantId, model, isRf, active])

  if (isRf) {
    return (
      <Card padded accent="graphite" className="mt-6 border-dashed border-graphite-700/80">
        <div className="flex items-start gap-3">
          <Info className="mt-0.5 h-5 w-5 flex-shrink-0 text-graphite-400" />
          <div>
            <h4 className="font-display text-sm font-semibold text-white">
              {isKn
                ? 'SHAP ವಿವರಣೆ ಲಭ್ಯವಿಲ್ಲ (ರ್ಯಾಂಡಮ್ ಫಾರೆಸ್ಟ್)'
                : 'SHAP Explainability Scope (Random Forest)'}
            </h4>
            <p className="mt-1 text-xs leading-relaxed text-graphite-300">
              {isKn
                ? 'SHAP ವಿವರಣೆಯನ್ನು ಸೌರ ಮತ್ತು ಪವನ LSTM ನರಮಂಡಲ ಮಾದರಿಗಳಿಗಾಗಿ ಅಳವಡಿಸಲಾಗಿದೆ. ರ್ಯಾಂಡಮ್ ಫಾರೆಸ್ಟ್ ಮಾದರಿಗೆ SHAP ಅನ್ವಯಿಸುವುದಿಲ್ಲ. LSTM ಮುನ್ಸೂಚನೆಯ ವಿವರಣೆಗಳನ್ನು ವೀಕ್ಷಿಸಲು ಮಾದರಿ ಪಟ್ಟಿಯಿಂದ "ಆಟೋ (ಶಿಫಾರಸು ಮಾಡಲಾಗಿದೆ)" ಅಥವಾ "LSTM" ಆಯ್ಕೆಮಾಡಿ.'
                : 'SHAP explainability is implemented for the active production Solar and Wind LSTM neural networks. Random Forest SHAP is excluded by policy. Please switch the model selector to "Auto (Recommended)" or "LSTM" to inspect neural network attributions.'}
            </p>
          </div>
        </div>
      </Card>
    )
  }

  // Pre-activation banner: keeps the Forecast page opening instantaneously!
  if (!active && !data) {
    return (
      <Card padded accent="brand" className="mt-6 border-brand-500/30 bg-graphite-900/90 shadow-xl backdrop-blur transition-all">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-brand-500/20 p-2.5 text-brand-400">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-display text-base font-bold text-white">
                  {isKn ? 'ಮುನ್ಸೂಚನೆ ವಿವರಣೆ · SHAP ಗುಣಲಕ್ಷಣಗಳು' : 'Explain Forecast · SHAP Attributions'}
                </h3>
                <Badge tone="brand" size="xs">
                  {renewableType || 'Solar'} LSTM
                </Badge>
              </div>
              <p className="mt-0.5 text-xs text-graphite-400">
                {isKn
                  ? 'ಉತ್ಪಾದನಾ LSTM ಮಾದರಿಯ ದೈನಂದಿನ ಬಿಂದು ಮುನ್ಸೂಚನೆಯ ಅಂಶವಾರು ಕೊಡುಗೆಗಳನ್ನು ಪರಿಶೀಲಿಸಿ.'
                  : 'Inspect mathematical Shapley feature attributions for this plant’s LSTM point forecast.'}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setActive(true)}
            className="flex items-center gap-2 rounded-lg bg-brand-500 hover:bg-brand-400 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-brand-500/25 transition-all active:scale-95"
          >
            <Sparkles className="h-4 w-4" />
            <span>{isKn ? 'SHAP ವಿವರಣೆ ರಚಿಸಿ' : 'Generate SHAP Explanation'}</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </Card>
    )
  }

  return (
    <Card padded className="mt-6 border-brand-500/30 bg-graphite-900/90 shadow-xl backdrop-blur">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-graphite-800 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="rounded-lg bg-brand-500/20 p-2 text-brand-400">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-display text-base font-bold text-white">
                {isKn ? 'ಮುನ್ಸೂಚನೆ ವಿವರಣೆ · SHAP ಗುಣಲಕ್ಷಣಗಳು' : 'Explain Forecast · SHAP Attributions'}
              </h3>
              <Badge tone="brand" size="xs">
                {data?.serving_model || `${renewableType || 'Solar'} LSTM (daily)`}
              </Badge>
            </div>
            <p className="mt-0.5 text-xs text-graphite-400">
              {isKn
                ? 'ಉತ್ಪಾದನಾ LSTM ಮಾದರಿಯ ದೈನಂದಿನ ಬಿಂದು ಮುನ್ಸೂಚನೆಯ ಅಂಶವಾರು ಕೊಡುಗೆಗಳು (SHAP KernelExplainer).'
                : 'Shapley feature contributions for the production LSTM point forecast relative to baseline.'}
            </p>
          </div>
        </div>

        {data && (
          <div className="flex items-center gap-2">
            <Badge tone="emerald" size="xs" className="flex items-center gap-1 font-mono">
              <CheckCircle2 className="h-3 w-3" />
              Diff: {Number(data.shapley_efficiency_diff || 0).toFixed(6)}
            </Badge>
            <span className="text-[11px] font-mono text-graphite-500">
              {data.compute_time_seconds ? `${data.compute_time_seconds}s` : ''}
            </span>
          </div>
        )}
      </div>

      {loading && (
        <div className="py-12">
          <LoadingState message={isKn ? 'SHAP ಗುಣಲಕ್ಷಣಗಳನ್ನು ಗಣನೆ ಮಾಡಲಾಗುತ್ತಿದೆ...' : 'Computing SHAP feature attributions...'} />
        </div>
      )}

      {error && !loading && (
        <div className="my-6 rounded-lg border border-rose-500/40 bg-rose-950/20 p-4 text-xs text-rose-300">
          <div className="flex items-center gap-2 font-semibold">
            <AlertCircle className="h-4 w-4" />
            {isKn ? 'ವಿವರಣೆ ಪಡೆಯಲು ವಿಫಲವಾಗಿದೆ' : 'Explanation Unavailable'}
          </div>
          <p className="mt-1 text-rose-400/90">{error}</p>
        </div>
      )}

      {!loading && !error && data && (
        <div className="mt-5 space-y-6">
          {/* Key Metric Summary Cards */}
          <div className="grid gap-3 sm:grid-cols-4">
            <div className="rounded-lg border border-graphite-700/60 bg-graphite-850/60 p-3">
              <span className="eyebrow">{isKn ? 'ವಿವರಿಸಲಾದ ಬಿಂದು ಮುನ್ಸೂಚನೆ' : 'Point Forecast Explained'}</span>
              <p className="mt-1 font-display text-lg font-bold text-white">
                {data.point_forecast?.toFixed(4)} <span className="text-xs font-normal text-graphite-400">{data.unit}</span>
              </p>
              <span className="text-[10px] text-graphite-500">Day 1 expected</span>
            </div>

            <div className="rounded-lg border border-graphite-700/60 bg-graphite-850/60 p-3">
              <span className="eyebrow">{isKn ? 'ತರಬೇತಿ ಬೇಸ್‌ಲೈನ್' : 'Training Baseline'}</span>
              <p className="mt-1 font-display text-lg font-bold text-graphite-200">
                {data.baseline_forecast?.toFixed(4)} <span className="text-xs font-normal text-graphite-400">{data.unit}</span>
              </p>
              <span className="text-[10px] text-graphite-500">Expected value E[f(x)]</span>
            </div>

            <div className="rounded-lg border border-graphite-700/60 bg-graphite-850/60 p-3">
              <span className="eyebrow">{isKn ? 'ಒಟ್ಟು ವೈಶಿಷ್ಟ್ಯಗಳ ಬದಲಾವಣೆ' : 'Net Feature Shift'}</span>
              <p className={`mt-1 font-display text-lg font-bold ${data.net_feature_contribution >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {data.net_feature_contribution >= 0 ? `+${data.net_feature_contribution?.toFixed(4)}` : data.net_feature_contribution?.toFixed(4)}{' '}
                <span className="text-xs font-normal text-graphite-400">{data.unit}</span>
              </p>
              <span className="text-[10px] text-graphite-500">Sum of SHAP values</span>
            </div>

            <div className="rounded-lg border border-graphite-700/60 bg-graphite-850/60 p-3">
              <span className="eyebrow">{isKn ? 'ಮುಖ್ಯ ಪ್ರಭಾವಿ ಅಂಶ' : 'Top Driving Factor'}</span>
              <p className="mt-1 truncate font-display text-sm font-bold text-brand-300">
                {data.feature_attributions?.[0]?.label || '—'}
              </p>
              <span className="text-[10px] text-graphite-400 font-mono">
                {data.feature_attributions?.[0]?.attribution > 0 ? '+' : ''}
                {data.feature_attributions?.[0]?.attribution?.toFixed(4)} {data.unit}
              </span>
            </div>
          </div>

          {/* Positive vs Negative Drivers Summary */}
          <div className="grid gap-4 md:grid-cols-2">
            {/* Positive Drivers */}
            <div className="rounded-lg border border-emerald-900/40 bg-emerald-950/20 p-3.5">
              <div className="flex items-center gap-1.5 font-semibold text-emerald-400 text-xs">
                <TrendingUp className="h-4 w-4" />
                <span>{isKn ? 'ಉತ್ಪಾದನೆಯನ್ನು ಹೆಚ್ಚಿಸಿದ ಅಂಶಗಳು (ಧನಾತ್ಮಕ)' : 'Factors Increasing Prediction (Positive Drivers)'}</span>
              </div>
              <div className="mt-2.5 space-y-2">
                {data.positive_factors && data.positive_factors.length > 0 ? (
                  data.positive_factors.slice(0, 3).map((f) => (
                    <div key={f.feature} className="flex items-center justify-between text-xs">
                      <span className="text-graphite-200">{f.label}</span>
                      <span className="font-mono font-semibold text-emerald-400">+{f.attribution?.toFixed(4)} {data.unit}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-graphite-400 italic">
                    {isKn ? 'ಯಾವುದೇ ಪ್ರಮುಖ ಧನಾತ್ಮಕ ಅಂಶಗಳಿಲ್ಲ' : 'No major positive contributors for this window'}
                  </p>
                )}
              </div>
            </div>

            {/* Negative Drivers */}
            <div className="rounded-lg border border-rose-900/40 bg-rose-950/20 p-3.5">
              <div className="flex items-center gap-1.5 font-semibold text-rose-400 text-xs">
                <TrendingDown className="h-4 w-4" />
                <span>{isKn ? 'ಉತ್ಪಾದನೆಯನ್ನು ಕುಗ್ಗಿಸಿದ ಅಂಶಗಳು (ಋಣಾತ್ಮಕ)' : 'Factors Decreasing Prediction (Negative Drivers)'}</span>
              </div>
              <div className="mt-2.5 space-y-2">
                {data.negative_factors && data.negative_factors.length > 0 ? (
                  data.negative_factors.slice(0, 3).map((f) => (
                    <div key={f.feature} className="flex items-center justify-between text-xs">
                      <span className="text-graphite-200">{f.label}</span>
                      <span className="font-mono font-semibold text-rose-400">{f.attribution?.toFixed(4)} {data.unit}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-graphite-400 italic">
                    {isKn ? 'ಯಾವುದೇ ಪ್ರಮುಖ ಋಣಾತ್ಮಕ ಅಂಶಗಳಿಲ್ಲ' : 'No major negative contributors for this window'}
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Ranked Feature Contribution Waterfall / Bar Chart */}
          <div>
            <div className="mb-2.5 flex items-center justify-between">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-graphite-300">
                {isKn ? 'ಶ್ರೇಣೀಕೃತ ವೈಶಿಷ್ಟ್ಯಗಳ ಕೊಡುಗೆ ಚಾರ್ಟ್' : 'Ranked Feature Contributions to Prediction'}
              </h4>
              <span className="text-[11px] text-graphite-500">
                {isKn ? 'ಶೂನ್ಯ ಕೇಂದ್ರಿತ ಪ್ರಭಾವ (MU/ದಿನ)' : 'Zero-centered impact (MU/day)'}
              </span>
            </div>

            <div className="space-y-2 rounded-lg border border-graphite-800 bg-graphite-950/60 p-4">
              {data.feature_attributions?.map((item) => {
                const maxAbs = Math.max(...data.feature_attributions.map((x) => x.abs_impact || 0.001), 0.001)
                const widthPercent = Math.min(100, Math.max(3, (item.abs_impact / maxAbs) * 100))
                const isPos = item.attribution >= 0

                return (
                  <div key={item.feature} className="group flex items-center gap-3 text-xs">
                    {/* Rank & Label */}
                    <div className="w-48 truncate flex items-center gap-1.5">
                      <span className="font-mono text-[10px] text-graphite-500 w-4">#{item.rank}</span>
                      <span className="font-medium text-graphite-200 group-hover:text-white transition-colors truncate" title={item.label}>
                        {item.label}
                      </span>
                    </div>

                    {/* Visual Bar Container */}
                    <div className="relative flex flex-1 items-center h-5 bg-graphite-900 rounded overflow-hidden">
                      {/* Zero baseline in center */}
                      <div className="absolute left-1/2 top-0 bottom-0 w-px bg-graphite-700 z-10" />

                      {isPos ? (
                        <div
                          className="absolute left-1/2 h-full bg-emerald-500/80 rounded-r transition-all duration-300 group-hover:bg-emerald-400"
                          style={{ width: `${widthPercent / 2}%` }}
                        />
                      ) : (
                        <div
                          className="absolute right-1/2 h-full bg-rose-500/80 rounded-l transition-all duration-300 group-hover:bg-rose-400"
                          style={{ width: `${widthPercent / 2}%` }}
                        />
                      )}
                    </div>

                    {/* Attribution Value & Latest Input Value */}
                    <div className="w-32 text-right font-mono flex flex-col justify-center">
                      <span className={`font-semibold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isPos ? `+${item.attribution.toFixed(4)}` : item.attribution.toFixed(4)}
                      </span>
                      <span className="text-[10px] text-graphite-500">
                        Obs: {item.latest_value}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Collapsible 7-Day Temporal Breakdown Matrix */}
          <div className="border-t border-graphite-800/80 pt-3">
            <button
              type="button"
              onClick={() => setShowTemporal(!showTemporal)}
              className="flex items-center gap-1.5 text-xs font-semibold text-brand-300 hover:text-brand-200 transition-colors"
            >
              <Calendar className="h-3.5 w-3.5" />
              <span>
                {showTemporal
                  ? (isKn ? '7-ದಿನಗಳ ಅನುಕ್ರಮ ಮ್ಯಾಟ್ರಿಕ್ಸ್ ಮುಚ್ಚಿ' : 'Hide 7-Day Input Sequence Breakdown')
                  : (isKn ? '7-ದಿನಗಳ ಅನುಕ್ರಮ ಮ್ಯಾಟ್ರಿಕ್ಸ್ ವೀಕ್ಷಿಸಿ' : 'Inspect 7-Day Temporal Sequence Matrix')}
              </span>
              {showTemporal ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </button>

            {showTemporal && data.temporal_breakdown && (
              <div className="mt-3 overflow-x-auto rounded-lg border border-graphite-800 bg-graphite-950 p-3">
                <table className="w-full text-left text-[11px]">
                  <thead>
                    <tr className="border-b border-graphite-800 text-graphite-400">
                      <th className="pb-2 font-semibold">Step / Day</th>
                      <th className="pb-2 font-semibold">Date</th>
                      <th className="pb-2 font-semibold text-right">Net Daily Impact</th>
                      <th className="pb-2 font-semibold text-right">Preceding Gen</th>
                      <th className="pb-2 font-semibold text-right">Weather Impact</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-graphite-850">
                    {data.temporal_breakdown.map((row) => (
                      <tr key={row.date} className="hover:bg-graphite-900/50">
                        <td className="py-1.5 font-medium text-graphite-300">{row.label}</td>
                        <td className="py-1.5 font-mono text-graphite-400">{row.date}</td>
                        <td className={`py-1.5 font-mono font-semibold text-right ${row.net_impact >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {row.net_impact >= 0 ? `+${row.net_impact.toFixed(4)}` : row.net_impact.toFixed(4)}
                        </td>
                        <td className="py-1.5 font-mono text-right text-graphite-300">
                          {row.feature_contributions?.Lagged_Generation?.toFixed(4) || '—'}
                        </td>
                        <td className="py-1.5 font-mono text-right text-graphite-400">
                          {((row.feature_contributions?.GHI || 0) + (row.feature_contributions?.WindSpeed || 0) + (row.feature_contributions?.Temperature || 0)).toFixed(4)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Scientific Disclaimer & Scope Distinction Notice */}
          <div className="rounded-lg border border-graphite-800 bg-graphite-950/70 p-3.5 text-[11px] leading-relaxed text-graphite-400">
            <div className="flex items-center gap-1.5 font-semibold text-graphite-300">
              <Info className="h-3.5 w-3.5 text-brand-400" />
              <span>{isKn ? 'ವಿಧಾನ ಮತ್ತು ಮಿತಿಗಳ ವಿವರಣೆ' : 'Explanation Scope & Methodological Assumptions'}</span>
            </div>
            <ul className="mt-1.5 list-disc list-inside space-y-1 text-graphite-400">
              <li>
                {isKn
                  ? 'SHAP ಮೌಲ್ಯಗಳು ನರಮಂಡಲ ಕಲಿತ ಸಂಬಂಧಗಳನ್ನು ವಿವರಿಸುತ್ತವೆ, ಭೌತಿಕ ಕಾರಣತ್ವವನ್ನಲ್ಲ.'
                  : 'SHAP KernelExplainer computes local additive Shapley feature attributions of the LSTM point forecast relative to the historical training baseline.'}
              </li>
              <li>
                <strong className="text-graphite-300">
                  {isKn ? 'ಅನಿಶ್ಚಿತತೆಯ ಶ್ರೇಣಿ ಪ್ರತ್ಯೇಕತೆ: ' : 'Point vs Interval Distinction: '}
                </strong>
                {isKn
                  ? 'ಈ ಗುಣಲಕ್ಷಣಗಳು ಬಿಂದು ಮುನ್ಸೂಚನೆಯನ್ನು ಮಾತ್ರ ವಿವರಿಸುತ್ತವೆ. P10/P50/P90 ಸಂಖ್ಯಾಶಾಸ್ತ್ರೀಯ ಶ್ರೇಣಿಯನ್ನು ಕಾನ್‌ಫಾರ್ಮಲ್ ಮಾಪನಾಂಕದಿಂದ ಪ್ರತ್ಯೇಕವಾಗಿ ನಿರ್ಧರಿಸಲಾಗಿದ್ದು, ಈ SHAP ಮೌಲ್ಯಗಳು ಆ ಶ್ರೇಣಿಯನ್ನು ವಿವರಿಸುವುದಿಲ್ಲ.'
                  : 'These attributions explain the neural network point prediction only. They do NOT explain the P10/P50/P90 uncertainty bounds, which are produced via separate conformal quantile calibration.'}
              </li>
              <li>
                {isKn
                  ? '7-ದಿನಗಳ ಅನುಕ್ರಮ ಕೊಡುಗೆಗಳನ್ನು ರೇಖೀಯ ಸಂಕಲನದಿಂದ ಒಟ್ಟುಗೂಡಿಸಲಾಗಿದೆ: attribution(f) = ∑_t φ(t, f).'
                  : 'Aggregated feature attributions represent the exact sum over the 7 time steps: attribution(f) = ∑_t φ(t, f). Efficiency difference is 0.000000.'}
              </li>
            </ul>
          </div>
        </div>
      )}
    </Card>
  )
}
