import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { api } from '../services/api'

export default function ABTestResults() {
  const [results, setResults] = useState([])

  useEffect(() => {
    api.abResults().then(setResults).catch(() => {})
  }, [])

  if (results.length === 0) {
    return (
      <div className="bg-slate-800/50 rounded-lg p-4">
        <h2 className="text-lg font-semibold text-white mb-3">A/B Test Results</h2>
        <p className="text-slate-500 text-sm">No A/B test data yet.</p>
      </div>
    )
  }

  // Group by role
  const byRole = {}
  results.forEach((r) => {
    if (!byRole[r.role]) byRole[r.role] = {}
    byRole[r.role][r.prompt_version] = {
      score: r.mean_score,
      count: r.total_calls,
    }
  })

  const chartData = Object.entries(byRole).map(([role, versions]) => ({
    role: role.replace('_', ' ').toUpperCase(),
    v1: versions.v1?.score || 0,
    v2: versions.v2?.score || 0,
    v1_count: versions.v1?.count || 0,
    v2_count: versions.v2?.count || 0,
  }))

  return (
    <div className="bg-slate-800/50 rounded-lg p-4">
      <h2 className="text-lg font-semibold text-white mb-3">A/B Test Results</h2>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="role" tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <YAxis domain={[0, 3]} tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
            labelStyle={{ color: '#e2e8f0' }}
          />
          <Legend wrapperStyle={{ color: '#94a3b8', fontSize: 12 }} />
          <Bar dataKey="v1" fill="#3b82f6" name="Prompt v1" radius={[4, 4, 0, 0]} />
          <Bar dataKey="v2" fill="#8b5cf6" name="Prompt v2" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-2 space-y-1">
        {chartData.map((d) => (
          <p key={d.role} className="text-xs text-slate-500">
            {d.role}: v1={d.v1.toFixed(2)} ({d.v1_count} calls) | v2={d.v2.toFixed(2)} ({d.v2_count} calls)
            {' '}
            {d.v1_count >= 5 && d.v2_count >= 5 && (
              <span className={d.v1 > d.v2 ? 'text-blue-400' : 'text-purple-400'}>
                Winner: {d.v1 > d.v2 ? 'v1' : 'v2'}
              </span>
            )}
          </p>
        ))}
      </div>
    </div>
  )
}
