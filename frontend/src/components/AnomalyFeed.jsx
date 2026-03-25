import { useState, useEffect } from 'react'
import { api } from '../services/api'

const SEVERITY_STYLES = {
  critical: 'border-red-500 bg-red-900/30 text-red-300',
  high: 'border-orange-500 bg-orange-900/30 text-orange-300',
  medium: 'border-yellow-500 bg-yellow-900/30 text-yellow-300',
  low: 'border-slate-500 bg-slate-800 text-slate-300',
}

export default function AnomalyFeed() {
  const [anomalies, setAnomalies] = useState([])

  useEffect(() => {
    api.anomalies().then(setAnomalies).catch(() => {})
  }, [])

  return (
    <div className="bg-slate-800/50 rounded-lg p-4">
      <h2 className="text-lg font-semibold text-white mb-3">Anomaly Feed</h2>
      {anomalies.length === 0 ? (
        <p className="text-slate-500 text-sm">No anomalies detected.</p>
      ) : (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {anomalies.slice(0, 10).map((a, i) => (
            <div
              key={i}
              className={`rounded border-l-4 p-3 ${SEVERITY_STYLES[a.severity] || SEVERITY_STYLES.low}`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase">{a.severity}</span>
                {a.city && <span className="text-xs opacity-70">{a.city}</span>}
              </div>
              <p className="text-sm mt-1">
                {a.metric}: {Math.abs(a.deviation_pct).toFixed(1)}% deviation
              </p>
              <p className="text-xs opacity-60 mt-0.5">
                Current: {a.current_value?.toLocaleString()} | Baseline: {a.baseline_value?.toLocaleString()}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
