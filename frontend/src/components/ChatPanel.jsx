import { useState, useRef, useEffect } from 'react'
import { api } from '../services/api'

export default function ChatPanel() {
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const startSession = async () => {
    try {
      const res = await api.chatStart()
      setSessionId(res.session_id)
      setMessages([{
        role: 'agent',
        text: 'Session started. Tell me your role — CEO, operations manager, or data analyst?',
        meta: { state: 'GREETING' },
      }])
    } catch (e) {
      setMessages([{ role: 'system', text: `Error: ${e.message}` }])
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || !sessionId || loading) return

    const userMsg = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', text: userMsg }])
    setLoading(true)

    try {
      const res = await api.chatMessage(sessionId, userMsg)
      setMessages((prev) => [...prev, {
        role: 'agent',
        text: res.response,
        meta: {
          role: res.role,
          state: res.state,
          sentiment: res.sentiment,
          tools: res.tool_calls,
          latency: res.latency_ms,
        },
      }])
    } catch (e) {
      setMessages((prev) => [...prev, { role: 'system', text: `Error: ${e.message}` }])
    } finally {
      setLoading(false)
    }
  }

  const endSession = async () => {
    if (sessionId) {
      await api.chatEnd(sessionId).catch(() => {})
      setSessionId(null)
      setMessages((prev) => [...prev, { role: 'system', text: 'Session ended.' }])
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="bg-slate-800/50 rounded-lg p-4 flex flex-col" style={{ height: '420px' }}>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-white">Chat with Agent</h2>
        {!sessionId ? (
          <button
            onClick={startSession}
            className="text-xs bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded"
          >
            New Session
          </button>
        ) : (
          <button
            onClick={endSession}
            className="text-xs bg-red-600/80 hover:bg-red-500 text-white px-3 py-1.5 rounded"
          >
            End Session
          </button>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto space-y-2 mb-3">
        {messages.length === 0 ? (
          <p className="text-slate-500 text-sm text-center mt-12">
            Click "New Session" to start chatting with the analytics agent.
          </p>
        ) : (
          messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : msg.role === 'system'
                  ? 'bg-slate-700 text-slate-400 text-xs'
                  : 'bg-slate-700 text-slate-200'
              }`}>
                <p className="whitespace-pre-wrap">{msg.text}</p>
                {msg.meta && (
                  <div className="flex gap-2 mt-1 text-xs opacity-60">
                    {msg.meta.role && <span>Role: {msg.meta.role}</span>}
                    {msg.meta.state && <span>State: {msg.meta.state}</span>}
                    {msg.meta.sentiment && <span>Mood: {msg.meta.sentiment}</span>}
                    {msg.meta.tools > 0 && <span>{msg.meta.tools} tools</span>}
                    {msg.meta.latency > 0 && <span>{(msg.meta.latency / 1000).toFixed(1)}s</span>}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      {sessionId && (
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={loading ? 'Agent is thinking...' : 'Type a message...'}
            disabled={loading}
            className="flex-1 bg-slate-700 text-white text-sm rounded px-3 py-2 border border-slate-600 focus:border-blue-500 focus:outline-none placeholder-slate-500 disabled:opacity-50"
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:hover:bg-blue-600 text-white text-sm px-4 py-2 rounded"
          >
            {loading ? '...' : 'Send'}
          </button>
        </div>
      )}
    </div>
  )
}
