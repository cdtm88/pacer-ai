import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { ChatBubble } from '@/components/chat/ChatBubble'
import { ChatInput } from '@/components/chat/ChatInput'
import { ChatScreen } from '@/screens/ChatScreen'
import { createConversation, sseUrl } from '@/lib/api'

// ---------------------------------------------------------------------------
// Module mocks -- hoisted before imports by Vitest
// ---------------------------------------------------------------------------

vi.mock('@/lib/api', () => ({
  createConversation: vi.fn().mockResolvedValue({
    id: 'conv-1',
    conversation_id: 'conv-1',
    user_id: 'u-1',
    title: null,
    created_at: '',
    updated_at: '',
  }),
  sseUrl: vi.fn().mockResolvedValue(
    'http://localhost:8000/chat/stream?conversation_id=conv-1&message=hi&token=tok',
  ),
}))

// ---------------------------------------------------------------------------
// MockEventSource (used in ChatScreen describe block)
// ---------------------------------------------------------------------------

class MockEventSource {
  static lastInstance: MockEventSource | null = null
  private _listeners: Map<string, EventListener[]> = new Map()
  close = vi.fn()

  constructor(public url: string) {
    MockEventSource.lastInstance = this
  }

  addEventListener(type: string, listener: EventListener) {
    const list = this._listeners.get(type) ?? []
    list.push(listener)
    this._listeners.set(type, list)
  }

  dispatch(type: string, data?: unknown) {
    const listeners = this._listeners.get(type) ?? []
    const event =
      data !== undefined
        ? new MessageEvent(type, { data: JSON.stringify(data) })
        : new Event(type)
    for (const listener of listeners) {
      listener(event)
    }
  }
}

// ---------------------------------------------------------------------------
// Wrapper for ChatScreen tests
// ---------------------------------------------------------------------------

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

// ---------------------------------------------------------------------------
// ChatBubble
// ---------------------------------------------------------------------------

describe('ChatBubble', () => {
  it('user bubble renders children in a span, positioned right', () => {
    const { container } = render(<ChatBubble role="user">Hello user</ChatBubble>)
    const outer = container.firstChild as HTMLElement
    expect(outer.className).toContain('items-end')
    const textEl = screen.getByText('Hello user')
    expect(textEl.tagName).toBe('SPAN')
  })

  it('coach bubble renders children via react-markdown with class markdown-body', () => {
    const { container } = render(<ChatBubble role="coach">Hello coach</ChatBubble>)
    expect(container.querySelector('.markdown-body')).not.toBeNull()
    expect(screen.getByText('Hello coach')).toBeInTheDocument()
  })

  it('isStreaming=true renders animated ellipsis and hides children', () => {
    render(
      <ChatBubble role="coach" isStreaming>
        Should not show
      </ChatBubble>,
    )
    expect(screen.getByLabelText('Coach is typing')).toBeInTheDocument()
    expect(screen.queryByText('Should not show')).toBeNull()
  })

  it('renders timestamp string when provided', () => {
    render(<ChatBubble role="coach" timestamp="3:45 PM">Content</ChatBubble>)
    expect(screen.getByText('3:45 PM')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// ChatInput
// ---------------------------------------------------------------------------

describe('ChatInput', () => {
  it('send button is disabled when value is empty', () => {
    render(<ChatInput onSend={vi.fn()} />)
    expect(screen.getByLabelText('Send message')).toBeDisabled()
  })

  it('send button is enabled when value is non-empty', () => {
    render(<ChatInput onSend={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Message input'), {
      target: { value: 'hello' },
    })
    expect(screen.getByLabelText('Send message')).not.toBeDisabled()
  })

  it('clicking Send calls onSend with trimmed text and clears the input', () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} />)
    const textarea = screen.getByLabelText('Message input') as HTMLTextAreaElement
    fireEvent.change(textarea, { target: { value: '  hello  ' } })
    fireEvent.click(screen.getByLabelText('Send message'))
    expect(onSend).toHaveBeenCalledWith('hello')
    expect(textarea.value).toBe('')
  })

  it('pressing Enter calls onSend', () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} />)
    const textarea = screen.getByLabelText('Message input')
    fireEvent.change(textarea, { target: { value: 'hi' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })
    expect(onSend).toHaveBeenCalledWith('hi')
  })

  it('pressing Shift+Enter does NOT call onSend', () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} />)
    const textarea = screen.getByLabelText('Message input')
    fireEvent.change(textarea, { target: { value: 'hi' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true })
    expect(onSend).not.toHaveBeenCalled()
  })

  it('disabled=true makes textarea and button disabled and onSend is not called on click', () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} disabled />)
    const textarea = screen.getByLabelText('Message input')
    const button = screen.getByLabelText('Send message')
    expect(textarea).toBeDisabled()
    expect(button).toBeDisabled()
    fireEvent.click(button)
    expect(onSend).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// ChatScreen
// ---------------------------------------------------------------------------

describe('ChatScreen', () => {
  beforeEach(() => {
    MockEventSource.lastInstance = null
    vi.stubGlobal('EventSource', MockEventSource)
    vi.clearAllMocks()
    // Re-apply default implementations after call-history clear
    vi.mocked(createConversation).mockResolvedValue({
      id: 'conv-1',
      conversation_id: 'conv-1',
      user_id: 'u-1',
      title: null,
      created_at: '',
      updated_at: '',
    })
    vi.mocked(sseUrl).mockResolvedValue(
      'http://localhost:8000/chat/stream?conversation_id=conv-1&message=hi&token=tok',
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows "Ask your coach anything" empty state before messages', () => {
    render(<ChatScreen />, { wrapper: Wrapper })
    expect(screen.getByText('Ask your coach anything')).toBeInTheDocument()
  })

  it('calls createConversation("Coaching session") on mount', async () => {
    render(<ChatScreen />, { wrapper: Wrapper })
    await waitFor(() => {
      expect(createConversation).toHaveBeenCalledWith('Coaching session')
    })
  })

  it('textarea is NOT disabled once conversation loads', async () => {
    render(<ChatScreen />, { wrapper: Wrapper })
    await waitFor(() => {
      expect(screen.getByLabelText('Message input')).not.toBeDisabled()
    })
  })

  it('typing a message and pressing Enter shows the user message immediately in the list', async () => {
    render(<ChatScreen />, { wrapper: Wrapper })
    await waitFor(() => expect(screen.getByLabelText('Message input')).not.toBeDisabled())

    const textarea = screen.getByLabelText('Message input')
    fireEvent.change(textarea, { target: { value: 'hi' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })

    expect(screen.getByText('hi')).toBeInTheDocument()
  })

  it('sseUrl is called with a path containing conversation_id=conv-1 and the encoded message', async () => {
    render(<ChatScreen />, { wrapper: Wrapper })
    await waitFor(() => expect(screen.getByLabelText('Message input')).not.toBeDisabled())

    const textarea = screen.getByLabelText('Message input')
    fireEvent.change(textarea, { target: { value: 'hi' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })

    await waitFor(() => {
      expect(sseUrl).toHaveBeenCalledWith(
        expect.stringContaining('conversation_id=conv-1'),
      )
    })
    // Drain the EventSource creation so it completes inside this test rather
    // than firing after afterEach unstubs the global (race between the React
    // scheduler macrotask and vi.unstubAllGlobals).
    await waitFor(() => expect(MockEventSource.lastInstance).not.toBeNull())
  })

  it('opens a new EventSource after sending a message', async () => {
    render(<ChatScreen />, { wrapper: Wrapper })
    await waitFor(() => expect(screen.getByLabelText('Message input')).not.toBeDisabled())

    const textarea = screen.getByLabelText('Message input')
    fireEvent.change(textarea, { target: { value: 'hi' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })

    await waitFor(() => expect(MockEventSource.lastInstance).not.toBeNull())
  })

  it('token events accumulate and the streaming coach bubble shows the content', async () => {
    render(<ChatScreen />, { wrapper: Wrapper })
    await waitFor(() => expect(screen.getByLabelText('Message input')).not.toBeDisabled())

    const textarea = screen.getByLabelText('Message input')
    fireEvent.change(textarea, { target: { value: 'hi' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })

    await waitFor(() => expect(MockEventSource.lastInstance).not.toBeNull())
    const es = MockEventSource.lastInstance!

    act(() => {
      es.dispatch('token', { text: 'Great question!' })
    })

    expect(screen.getByText('Great question!')).toBeInTheDocument()
  })

  it('textarea is disabled while streaming (after send, before done)', async () => {
    render(<ChatScreen />, { wrapper: Wrapper })
    await waitFor(() => expect(screen.getByLabelText('Message input')).not.toBeDisabled())

    const textarea = screen.getByLabelText('Message input')
    fireEvent.change(textarea, { target: { value: 'hi' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })

    await waitFor(() => {
      expect(screen.getByLabelText('Message input')).toBeDisabled()
    })
  })

  it('after done event, accumulated coach message appears in list and textarea re-enables', async () => {
    render(<ChatScreen />, { wrapper: Wrapper })
    await waitFor(() => expect(screen.getByLabelText('Message input')).not.toBeDisabled())

    const textarea = screen.getByLabelText('Message input')
    fireEvent.change(textarea, { target: { value: 'hi' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })

    await waitFor(() => expect(MockEventSource.lastInstance).not.toBeNull())
    const es = MockEventSource.lastInstance!

    act(() => {
      es.dispatch('token', { text: 'Great question!' })
    })
    act(() => {
      es.dispatch('done')
    })

    await waitFor(() => {
      expect(screen.getByText('Great question!')).toBeInTheDocument()
      expect(screen.getByLabelText('Message input')).not.toBeDisabled()
    })
  })

  // ---------------------------------------------------------------------------
  // Item 3 (D-03): empty-done-swallow fix -- a tool-only turn (done + empty
  // content) must always clear activeStreamUrl/pendingUserMessage, silently,
  // so a subsequent send is never bricked.
  // ---------------------------------------------------------------------------

  it('a done event with empty content (tool-only turn) clears activeStreamUrl silently and unbricks a subsequent send', async () => {
    render(<ChatScreen />, { wrapper: Wrapper })
    await waitFor(() => expect(screen.getByLabelText('Message input')).not.toBeDisabled())

    const textarea = screen.getByLabelText('Message input')
    fireEvent.change(textarea, { target: { value: 'hi' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })

    await waitFor(() => expect(MockEventSource.lastInstance).not.toBeNull())
    const firstEs = MockEventSource.lastInstance!

    act(() => {
      firstEs.dispatch('done') // no content -- tool-only turn
    })

    await waitFor(() => {
      expect(screen.getByLabelText('Message input')).not.toBeDisabled()
    })
    // No coach bubble was pushed for the empty-content done -- render nothing extra
    expect(screen.queryByText('Great question!')).toBeNull()

    // A subsequent send must succeed -- previously bricked forever because
    // activeStreamUrl was never nulled for an empty-content done.
    fireEvent.change(textarea, { target: { value: 'second message' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })

    await waitFor(() => {
      expect(MockEventSource.lastInstance).not.toBe(firstEs)
    })
    expect(screen.getByText('second message')).toBeInTheDocument()
  })

  it('a done event with non-empty content pushes exactly one coach message and clears activeStreamUrl for a subsequent send', async () => {
    render(<ChatScreen />, { wrapper: Wrapper })
    await waitFor(() => expect(screen.getByLabelText('Message input')).not.toBeDisabled())

    const textarea = screen.getByLabelText('Message input')
    fireEvent.change(textarea, { target: { value: 'hi' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })

    await waitFor(() => expect(MockEventSource.lastInstance).not.toBeNull())
    const firstEs = MockEventSource.lastInstance!

    act(() => {
      firstEs.dispatch('token', { text: 'Great question!' })
    })
    act(() => {
      firstEs.dispatch('done')
    })

    await waitFor(() => {
      expect(screen.getAllByText('Great question!')).toHaveLength(1)
      expect(screen.getByLabelText('Message input')).not.toBeDisabled()
    })

    fireEvent.change(textarea, { target: { value: 'second message' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })

    await waitFor(() => {
      expect(MockEventSource.lastInstance).not.toBe(firstEs)
    })
  })

  // ---------------------------------------------------------------------------
  // Item 2 (D-02): terminal stream error (retries exhausted) renders
  // StreamErrorBanner with a manual Retry, and the input re-enables. The
  // stale "Connection lost. Reconnecting..." permanent banner no longer
  // appears (Pitfall 3).
  // ---------------------------------------------------------------------------

  it('terminal stream error (after retries exhaust) renders StreamErrorBanner with Retry, and the input re-enables', async () => {
    render(<ChatScreen />, { wrapper: Wrapper })
    await waitFor(() => expect(screen.getByLabelText('Message input')).not.toBeDisabled())

    const textarea = screen.getByLabelText('Message input')
    fireEvent.change(textarea, { target: { value: 'hi' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })

    await waitFor(() => expect(MockEventSource.lastInstance).not.toBeNull())

    vi.useFakeTimers()
    try {
      let es = MockEventSource.lastInstance!
      act(() => {
        es.dispatch('error', { message: 'fail 1' })
      })
      act(() => {
        vi.advanceTimersByTime(500)
      })
      es = MockEventSource.lastInstance!
      act(() => {
        es.dispatch('error', { message: 'fail 2' })
      })
      act(() => {
        vi.advanceTimersByTime(1500)
      })
      es = MockEventSource.lastInstance!
      act(() => {
        es.dispatch('error', { message: 'fail 3 terminal' })
      })

      expect(screen.getByText('Connection failed.')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
      expect(screen.getByLabelText('Message input')).not.toBeDisabled()
      expect(screen.queryByText('Connection lost. Reconnecting...')).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  it('clicking Retry re-derives the stream URL from the last sent message and re-enters streaming, clearing the banner', async () => {
    render(<ChatScreen />, { wrapper: Wrapper })
    await waitFor(() => expect(screen.getByLabelText('Message input')).not.toBeDisabled())

    const textarea = screen.getByLabelText('Message input')
    fireEvent.change(textarea, { target: { value: 'hi' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })

    await waitFor(() => expect(MockEventSource.lastInstance).not.toBeNull())
    const firstEs = MockEventSource.lastInstance!
    const callsBeforeRetry = vi.mocked(sseUrl).mock.calls.length

    vi.useFakeTimers()
    try {
      let es = firstEs
      act(() => {
        es.dispatch('error', { message: 'fail 1' })
      })
      act(() => {
        vi.advanceTimersByTime(500)
      })
      es = MockEventSource.lastInstance!
      act(() => {
        es.dispatch('error', { message: 'fail 2' })
      })
      act(() => {
        vi.advanceTimersByTime(1500)
      })
      es = MockEventSource.lastInstance!
      act(() => {
        es.dispatch('error', { message: 'fail 3 terminal' })
      })

      expect(screen.getByText('Connection failed.')).toBeInTheDocument()

      const retryButton = screen.getByRole('button', { name: /retry/i })
      await act(async () => {
        fireEvent.click(retryButton)
      })

      expect(vi.mocked(sseUrl).mock.calls.length).toBeGreaterThan(callsBeforeRetry)
      expect(vi.mocked(sseUrl).mock.calls.at(-1)?.[0]).toContain('message=hi')
      expect(screen.queryByText('Connection failed.')).toBeNull()
      expect(screen.getByLabelText('Message input')).toBeDisabled()
    } finally {
      vi.useRealTimers()
    }
  })
})
