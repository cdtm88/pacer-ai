import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ---------------------------------------------------------------------------
// Real exportSessionZwo tests (items 6, 7)
//
// zwo-modal.test.tsx mocks '@/lib/api' at the module level (it tests
// ZwoExportModal's UI behavior against a stubbed exportSessionZwo), so it
// cannot exercise the REAL parsing/ordering logic inside exportSessionZwo
// itself. This sibling file exercises the real implementation against a
// mocked fetch/supabase session, per 09-03-PLAN.md Task 2's read_first note.
// ---------------------------------------------------------------------------

vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: 'test-token' } },
      }),
    },
  },
}))

import { exportSessionZwo } from '../lib/api'

function makeResponse(overrides: Partial<Response> & { jsonImpl?: () => unknown } = {}): Response {
  const { jsonImpl, ...rest } = overrides
  return {
    ok: false,
    status: 404,
    headers: new Headers(),
    json: jsonImpl ? vi.fn(jsonImpl) : vi.fn().mockResolvedValue({}),
    blob: vi.fn().mockResolvedValue(new Blob()),
    ...rest,
  } as unknown as Response
}

describe('exportSessionZwo (item 6 — error-shape parsing)', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('throws the backend error/detail string for a session_not_found 404, not a bare status code', async () => {
    vi.mocked(fetch).mockResolvedValue(
      makeResponse({
        status: 404,
        jsonImpl: () => ({
          detail: { error: 'session_not_found', detail: 'No session found for this user with the given id' },
        }),
      })
    )

    await expect(exportSessionZwo('session-1')).rejects.toThrow(/session_not_found/)
  })

  it('falls back to the status-code message when the error body is not valid JSON', async () => {
    vi.mocked(fetch).mockResolvedValue(
      makeResponse({
        status: 500,
        jsonImpl: () => {
          throw new SyntaxError('Unexpected token')
        },
      })
    )

    await expect(exportSessionZwo('session-1')).rejects.toThrow('export failed 500')
  })
})

describe('exportSessionZwo (item 7 — iOS gesture-safe window ordering)', () => {
  const originalUserAgent = navigator.userAgent

  function setUserAgent(ua: string) {
    Object.defineProperty(navigator, 'userAgent', { value: ua, configurable: true })
  }

  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    setUserAgent(originalUserAgent)
  })

  it('on iOS, opens the window BEFORE the fetch promise resolves (inside the gesture window)', async () => {
    setUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15')

    let resolveFetch!: (r: Response) => void
    const pendingFetch = new Promise<Response>((resolve) => {
      resolveFetch = resolve
    })
    vi.mocked(fetch).mockReturnValue(pendingFetch)

    const fakeWindow = { location: { href: '' }, close: vi.fn() }
    const openSpy = vi.spyOn(window, 'open').mockReturnValue(fakeWindow as unknown as Window)

    // Call without awaiting — fetch is still pending, so if window.open has
    // already been called synchronously, it proves the call happened before
    // any await, i.e. inside the original click gesture.
    const exportPromise = exportSessionZwo('session-1')

    expect(openSpy).toHaveBeenCalledTimes(1)
    expect(openSpy).toHaveBeenCalledWith('', '_blank')

    // Resolve the fetch so the promise settles cleanly (avoid unhandled rejection noise).
    resolveFetch(
      makeResponse({
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Disposition': 'attachment; filename="workout.zwo"' }),
      })
    )
    await exportPromise
    expect(fakeWindow.location.href).toContain('blob:')
  })

  it('on non-iOS, does not call window.open and uses the hidden-anchor download path', async () => {
    setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')

    vi.mocked(fetch).mockResolvedValue(
      makeResponse({
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Disposition': 'attachment; filename="workout.zwo"' }),
      })
    )
    const openSpy = vi.spyOn(window, 'open')
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    await exportSessionZwo('session-1')

    expect(openSpy).not.toHaveBeenCalled()
    expect(clickSpy).toHaveBeenCalledTimes(1)
  })
})
