import { useEffect, useState } from 'react'

// ---------------------------------------------------------------------------
// SSE event types emitted by the backend (_sse.py)
//   event: token         data: {"text": "..."}
//   event: tool_start    data: {"name": "...", "tool_use_id": "toolu_..."}
//   event: tool_result   data: {"tool_use_id": "...", "name": "...", "value": ...}
//   event: done          data: {}
//   event: error         data: {"code": "...", "message": "..."}
//
// The url MUST already include ?token=<jwt> because EventSource cannot send
// Authorization headers (Pitfall 1 from RESEARCH.md). Use the sseUrl() helper
// from api.ts to construct the url before passing it here.
// ---------------------------------------------------------------------------

export interface SSEStreamState {
  content: string
  isDone: boolean
  isThinking: boolean
  error: string | null
}

export function useSSEStream(url: string | null): SSEStreamState {
  const [content, setContent] = useState('')
  const [isDone, setIsDone] = useState(false)
  const [isThinking, setIsThinking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!url) return

    // Reset state on each new url
    setContent('')
    setIsDone(false)
    setIsThinking(false)
    setError(null)

    const es = new EventSource(url)

    // Track whether the stream completed successfully to suppress the spurious
    // error event that EventSource fires when the server closes the connection
    // after the done event (WR-002).
    let streamCompleted = false

    // token: append streamed text to the accumulating content buffer
    es.addEventListener('token', (e: MessageEvent) => {
      try {
        const { text } = JSON.parse(e.data) as { text: string }
        setContent((prev) => prev + text)
      } catch {
        // malformed token event -- ignore
      }
    })

    // tool_start: show thinking indicator while tool is running
    es.addEventListener('tool_start', () => {
      setIsThinking(true)
    })

    // tool_result: tool finished; clear thinking indicator
    es.addEventListener('tool_result', () => {
      setIsThinking(false)
    })

    // done: stream complete; close the EventSource
    es.addEventListener('done', () => {
      streamCompleted = true
      setIsDone(true)
      setIsThinking(false)
      es.close()
    })

    // error: surface message and close; ignore post-done connection-close events
    es.addEventListener('error', (e: Event) => {
      if (streamCompleted) return // EventSource fires error on normal server close after done
      try {
        const data = JSON.parse((e as MessageEvent).data) as {
          code?: string
          message?: string
        }
        setError(data.message ?? 'Stream error')
      } catch {
        setError('Stream error')
      }
      setIsThinking(false)
      es.close()
    })

    return () => {
      es.close()
    }
  }, [url])

  return { content, isDone, isThinking, error }
}
