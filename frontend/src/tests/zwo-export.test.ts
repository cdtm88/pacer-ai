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
