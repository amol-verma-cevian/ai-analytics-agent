import { useState, useEffect } from 'react'
import { api } from '../services/api'

function Card({ title, value, sub, color = 'blue' }) {
  const colors = {
    blue: 'border-blue-500 bg-blue-500/10',
    green: 'border-green-500 bg-green-500/10',
    red: 'border-red-500 bg-red-500/10',
    yellow: 'border-yellow-500 bg-yellow-500/10',
  }
  return (
    <div className={`rounded-lg border-l-4 ${colors[color]} p-4`}>
      <p className="text-sm text-slate-400">{title}</p>
      <p className="text-2xl font-bold text-white mt-1">{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  )
}

export default function MetricCards() {
  const [data, setData] = useState(null)
  const [week, setWeek] = useState(null)

  useEffect(() => {
    api.ceoSummary().then(setData).catch(() => {})
    api.weekComparison().then(setWeek).catch(() => {})
  }, [])

  if (!data) return <div className="text-slate-500 p-4">Loading metrics...</div>

  const fmt = (n) => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
    return n.toString()
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <Card
        title="Total Orders"
        value={fmt(data.total_orders)}
        sub={`Yesterday (${data.date})`}
        color="blue"
      />
      <Card
        title="Revenue"
        value={`Rs ${fmt(data.total_revenue)}`}
        sub="Gross revenue"
        color="green"
      />
      <Card
        title="Cancel Rate"
        value={`${data.cancellation_rate}%`}
        sub="Of total orders"
        color={data.cancellation_rate > 5 ? 'red' : 'yellow'}
      />
      <Card
        title="Week Trend"
        value={week ? `${week.change_pct > 0 ? '+' : ''}${week.change_pct}%` : '...'}
        sub={week ? `${fmt(week.this_week_orders)} vs ${fmt(week.last_week_orders)}` : ''}
        color={week?.change_pct >= 0 ? 'green' : 'red'}
      />
    </div>
  )
}
