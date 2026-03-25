import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { api } from '../services/api'

export default function EvalScores() {
  const [evals, setEvals] = useState([])

  useEffect(() => {
    api.evaluations().then(setEvals).catch(() => {})
  }, [])

  if (evals.length === 0) {
    return (
      <div className="bg-slate-800/50 rounded-lg p-4">
        <h2 className="text-lg font-semibold text-white mb-3">Evaluation Scores</h2>
        <p className="text-slate-500 text-sm">No evaluations yet.</p>
      </div>
    )
  }

  // Calculate averages across all evaluations
  const dims = ['accuracy', 'factual_correctness', 'stability', 'response_style', 'conversational_coherence']
  const chartData = dims.map((dim) => {
    const values = evals.map((e) => e[dim]).filter(Boolean)
    const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0
    return {
      name: dim.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      score: parseFloat(avg.toFixed(2)),
      fill: avg >= 2.5 ? '#22c55e' : avg >= 2.0 ? '#eab308' : '#ef4444',
    }
  })

  const overall = chartData.reduce((s, d) => s + d.score, 0) / chartData.length

  return (
    <div className="bg-slate-800/50 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-white">Evaluation Scores</h2>
        <span className={`text-sm font-bold px-2 py-1 rounded ${
          overall >= 2.5 ? 'bg-green-900 text-green-300' :
          overall >= 2.0 ? 'bg-yellow-900 text-yellow-300' :
          'bg-red-900 text-red-300'
        }`}>
          {overall.toFixed(1)}/3
        </span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 80 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis type="number" domain={[0, 3]} tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <YAxis type="category" dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} width={90} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
            labelStyle={{ color: '#e2e8f0' }}
          />
          <Bar dataKey="score" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
      <p className="text-xs text-slate-500 mt-2">{evals.length} evaluations total</p>
    </div>
  )
}
