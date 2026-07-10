import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router'
import { AppLayout } from '@/components/AppLayout'

// ---------------------------------------------------------------------------
// AppLayout height-chain regression test (09-05, item 9).
// Both wrapping divs must use h-dvh (not min-h-screen/h-screen) so the chat
// input stays pinned and inner scroll panes work on iOS Safari
// (09-RESEARCH.md Pitfall 4). This is a lightweight class-presence check;
// the definitive pinned-input/auto-scroll behavior is manual-only
// (09-VALIDATION.md).
//
// ADAPT-04 (13-02): AppLayout now mounts useAdaptationCheck(), which calls
// checkAdaptations() from ../lib/api. Stub it here so it resolves harmlessly
// during render and doesn't touch the network in this test.
// ---------------------------------------------------------------------------

vi.mock('../lib/api', () => ({
  checkAdaptations: vi.fn().mockResolvedValue({}),
}))

describe('AppLayout height chain', () => {
  it('both wrapping containers use h-dvh and neither uses min-h-screen', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<div>content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    )

    const outer = container.querySelector('.h-dvh')
    expect(outer).not.toBeNull()

    const inner = container.querySelector('.md\\:ml-60')
    expect(inner).not.toBeNull()
    expect(inner?.className).toContain('h-dvh')
    expect(inner?.className).not.toContain('min-h-screen')
    expect(outer?.className).not.toContain('min-h-screen')
  })
})
