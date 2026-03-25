import { useState, useEffect } from 'react'
import { api } from '../services/api'

const TRIGGER_LABELS = {
  explicit: 'User requested',
  sentiment: 'Frustrated user',
  confidence: 'Low AI confidence',
  turn_count: 'Too many turns',
}

const SEVERITY_DOT = {
  high: 'bg-red-400',
  medium: 'bg-yellow-400',
  low: 'bg-slate-400',
}

export default function EscalationPanel({ events }) {
  const [escalations, setEscalations] = useState([])

  useEffect(() => {
    api.escalations().then(setEscalations).catch(() => {})
  }, [])

  // Merge DB escalations with live WS events
  const liveEscalations = events
    .filter((e) => e.event === 'escalation')
    .map((e) => ({
      call_id: e.data.call_id,
      trigger: e.data.trigger,
      severity: e.data.severity,
      reason: e.data.reason,
      created_at: e.data.timestamp,
    }))

  const all = [...liveEscalations, ...escalations].slice(0, 10)

  // Calculate escalation rate from events
  const totalCalls = events.filter((e) => e.event === 'call_started').length
  const totalEscalations = events.filter((e) => e.event === 'escalation').length
  const rate = totalCalls > 0 ? ((totalEscalations / totalCalls) * 100).toFixed(0) : '0'

  return (
    <div className="bg-slate-800/50 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-white">Escalations</h2>
        <span className={`text-sm font-bold px-2 py-1 rounded ${
          parseInt(rate) > 15 ? 'bg-red-900 text-red-300' :
          parseInt(rate) > 5 ? 'bg-yellow-900 text-yellow-300' :
          'bg-green-900 text-green-300'
        }`}>
          {rate}% rate
        </span>
      </div>

      {all.length === 0 ? (
        <p className="text-slate-500 text-sm">No escalations. AI handling all calls.</p>
      ) : (
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {all.map((e, i) => (
            <div key={i} className="flex items-start gap-2 py-1.5 border-b border-slate-700/50">
              <span className={`w-2 h-2 mt-1.5 rounded-full ${SEVERITY_DOT[e.severity] || 'bg-slate-400'}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-slate-300">
                    {TRIGGER_LABELS[e.trigger] || e.trigger}
                  </span>
                  <span className="text-xs text-slate-600 ml-auto">
                    {e.call_id?.slice(0, 8)}
                  </span>
                </div>
                <p className="text-xs text-slate-500 truncate">{e.reason}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
