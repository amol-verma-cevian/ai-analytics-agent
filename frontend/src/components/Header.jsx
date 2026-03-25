export default function Header({ connected }) {
  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
      <div>
        <h1 className="text-xl font-bold text-white">AI Analytics Dashboard</h1>
        <p className="text-sm text-slate-400">Intelligent Briefing Agent</p>
      </div>
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-red-400'}`} />
        <span className="text-sm text-slate-400">
          {connected ? 'Live' : 'Disconnected'}
        </span>
      </div>
    </header>
  )
}
