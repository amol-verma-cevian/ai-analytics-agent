import { useState, useEffect, useRef, useCallback } from 'react'

const WS_URL = `ws://${window.location.hostname}:8000/ws`

export function useWebSocket() {
  const [events, setEvents] = useState([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        if (reconnectRef.current) {
          clearTimeout(reconnectRef.current)
          reconnectRef.current = null
        }
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          setEvents((prev) => [data, ...prev].slice(0, 100))
        } catch (e) {
          console.error('WS parse error:', e)
        }
      }

      ws.onclose = () => {
        setConnected(false)
        reconnectRef.current = setTimeout(connect, 3000)
      }

      ws.onerror = () => {
        ws.close()
      }
    } catch (e) {
      setConnected(false)
      reconnectRef.current = setTimeout(connect, 3000)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (wsRef.current) wsRef.current.close()
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
    }
  }, [connect])

  return { events, connected }
}
