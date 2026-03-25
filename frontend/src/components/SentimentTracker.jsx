const SENTIMENT_CONFIG = {
  satisfied: { color: 'bg-green-500', label: 'Satisfied', emoji: '+' },
  neutral: { color: 'bg-slate-500', label: 'Neutral', emoji: '~' },
  frustrated: { color: 'bg-red-500', label: 'Frustrated', emoji: '!' },
}

export default function SentimentTracker({ events }) {
  const sentimentEvents = events
    .filter((e) => e.event === 'user_spoke' && e.data?.sentiment)
    .slice(0, 20)

  const counts = { satisfied: 0, neutral: 0, frustrated: 0 }
  sentimentEvents.forEach((e) => {
    const s = e.data.sentiment
    if (counts[s] !== undefined) counts[s]++
  })
  const total = sentimentEvents.length || 1

  return (
    <div className="bg-slate-800/50 rounded-lg p-4">
      <h2 className="text-lg font-semibold text-white mb-3">Sentiment Tracker</h2>
      {sentimentEvents.length === 0 ? (
        <p className="text-slate-500 text-sm">No sentiment data yet.</p>
      ) : (
        <>
          {/* Bar visualization */}
          <div className="flex h-4 rounded-full overflow-hidden mb-3">
            {counts.satisfied > 0 && (
              <div
                className="bg-green-500 transition-all"
                style={{ width: `${(counts.satisfied / total) * 100}%` }}
              />
            )}
            {counts.neutral > 0 && (
              <div
                className="bg-slate-500 transition-all"
                style={{ width: `${(counts.neutral / total) * 100}%` }}
              />
            )}
            {counts.frustrated > 0 && (
              <div
                className="bg-red-500 transition-all"
                style={{ width: `${(counts.frustrated / total) * 100}%` }}
              />
            )}
          </div>

          {/* Legend */}
          <div className="flex gap-4 text-sm">
            {Object.entries(SENTIMENT_CONFIG).map(([key, cfg]) => (
              <div key={key} className="flex items-center gap-1.5">
                <span className={`w-2.5 h-2.5 rounded-full ${cfg.color}`} />
                <span className="text-slate-400">
                  {cfg.label}: {counts[key]}
                </span>
              </div>
            ))}
          </div>

          {/* Recent entries */}
          <div className="mt-3 space-y-1 max-h-32 overflow-y-auto">
            {sentimentEvents.slice(0, 8).map((e, i) => {
              const cfg = SENTIMENT_CONFIG[e.data.sentiment] || SENTIMENT_CONFIG.neutral
              return (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className={`w-1.5 h-1.5 rounded-full ${cfg.color}`} />
                  <span className="text-slate-500 truncate flex-1">
                    "{e.data.user_text?.slice(0, 50)}"
                  </span>
                  <span className="text-slate-600">{cfg.label}</span>
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
