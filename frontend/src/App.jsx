import { useWebSocket } from './hooks/useWebSocket'
import Header from './components/Header'
import MetricCards from './components/MetricCards'
import ChatPanel from './components/ChatPanel'
import LiveCallFeed from './components/LiveCallFeed'
import EvalScores from './components/EvalScores'
import ABTestResults from './components/ABTestResults'
import AnomalyFeed from './components/AnomalyFeed'
import SentimentTracker from './components/SentimentTracker'
import EscalationPanel from './components/EscalationPanel'
import CallHistory from './components/CallHistory'

export default function App() {
  const { events, connected } = useWebSocket()

  return (
    <div className="min-h-screen bg-slate-900">
      <Header connected={connected} />

      <main className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Row 1: Metric Cards */}
        <MetricCards />

        {/* Row 2: Chat + Live Feed */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ChatPanel />
          <LiveCallFeed events={events} />
        </div>

        {/* Row 3: Anomalies + Eval Scores */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <AnomalyFeed />
          <EvalScores />
        </div>

        {/* Row 4: A/B Testing + Sentiment */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ABTestResults />
          <SentimentTracker events={events} />
        </div>

        {/* Row 5: Escalations + Call History */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <EscalationPanel events={events} />
          <CallHistory />
        </div>
      </main>
    </div>
  )
}
