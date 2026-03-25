const EVENT_COLORS = {
  call_started: 'text-green-400',
  call_ended: 'text-slate-400',
  user_spoke: 'text-blue-400',
  escalation: 'text-red-400',
}

const EVENT_ICONS = {
  call_started: 'ring-2 ring-green-400',
  call_ended: 'ring-2 ring-slate-500',
  user_spoke: 'ring-2 ring-blue-400',
  escalation: 'ring-2 ring-red-400',
}

function formatTime(ts) {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleTimeString()
  } catch {
    return ts
  }
}

export default function LiveCallFeed({ events }) {
  const relevant = events.filter((e) =>
    ['call_started', 'call_ended', 'user_spoke', 'escalation'].includes(e.event)
  )

  if (relevant.length === 0) {
    return (
      <div className="bg-slate-800/50 rounded-lg p-4">
        <h2 className="text-lg font-semibold text-white mb-3">Live Call Feed</h2>
        <p className="text-slate-500 text-sm">No events yet. Waiting for calls...</p>
      </div>
    )
  }

  return (
    <div className="bg-slate-800/50 rounded-lg p-4">
      <h2 className="text-lg font-semibold text-white mb-3">Live Call Feed</h2>
      <div className="space-y-2 max-h-80 overflow-y-auto">
        {relevant.slice(0, 20).map((e, i) => (
          <div key={i} className="flex items-start gap-3 py-2 border-b border-slate-700/50">
            <span className={`w-2 h-2 mt-2 rounded-full ${EVENT_ICONS[e.event]}`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={`text-sm font-medium ${EVENT_COLORS[e.event]}`}>
                  {e.event.replace('_', ' ')}
                </span>
                {e.data?.role && (
                  <span className="text-xs bg-slate-700 px-1.5 py-0.5 rounded">
                    {e.data.role}
                  </span>
                )}
                {e.data?.sentiment && e.data.sentiment !== 'neutral' && (
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    e.data.sentiment === 'frustrated' ? 'bg-red-900 text-red-300' : 'bg-green-900 text-green-300'
                  }`}>
                    {e.data.sentiment}
                  </span>
                )}
                <span className="text-xs text-slate-500 ml-auto">
                  {formatTime(e.data?.timestamp)}
                </span>
              </div>
              {e.data?.user_text && (
                <p className="text-sm text-slate-300 mt-1 truncate">
                  "{e.data.user_text}"
                </p>
              )}
              {e.data?.agent_response && (
                <p className="text-xs text-slate-500 mt-0.5 truncate">
                  Agent: {e.data.agent_response}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
