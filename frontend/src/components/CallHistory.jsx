import { useState, useEffect } from 'react'
import { api } from '../services/api'

const STATE_BADGE = {
  GREETING: 'bg-blue-900 text-blue-300',
  ROLE_DETECTION: 'bg-purple-900 text-purple-300',
  BRIEFING: 'bg-green-900 text-green-300',
  DRILL_DOWN: 'bg-yellow-900 text-yellow-300',
  FOLLOW_UP: 'bg-cyan-900 text-cyan-300',
  CLOSING: 'bg-slate-700 text-slate-300',
}

export default function CallHistory() {
  const [calls, setCalls] = useState([])

  useEffect(() => {
    api.calls().then(setCalls).catch(() => {})
  }, [])

  return (
    <div className="bg-slate-800/50 rounded-lg p-4">
      <h2 className="text-lg font-semibold text-white mb-3">Call History</h2>
      {calls.length === 0 ? (
        <p className="text-slate-500 text-sm">No call history.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-400 text-xs border-b border-slate-700">
                <th className="text-left py-2 pr-3">Call ID</th>
                <th className="text-left py-2 pr-3">Direction</th>
                <th className="text-left py-2 pr-3">Role</th>
                <th className="text-left py-2 pr-3">State</th>
                <th className="text-left py-2 pr-3">Turns</th>
                <th className="text-left py-2">Escalated</th>
              </tr>
            </thead>
            <tbody>
              {calls.slice(0, 15).map((c, i) => (
                <tr key={i} className="border-b border-slate-700/30 hover:bg-slate-700/20">
                  <td className="py-2 pr-3 text-slate-300 font-mono text-xs">
                    {c.call_id?.slice(0, 12)}
                  </td>
                  <td className="py-2 pr-3">
                    <span className={c.direction === 'outbound' ? 'text-purple-400' : 'text-blue-400'}>
                      {c.direction}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-slate-400">{c.role_detected || c.role || '-'}</td>
                  <td className="py-2 pr-3">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${STATE_BADGE[c.state] || 'bg-slate-700 text-slate-400'}`}>
                      {c.state}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-slate-400">{c.total_turns}</td>
                  <td className="py-2">
                    {c.escalated ? (
                      <span className="text-xs bg-red-900 text-red-300 px-1.5 py-0.5 rounded">Yes</span>
                    ) : (
                      <span className="text-xs text-slate-600">No</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
