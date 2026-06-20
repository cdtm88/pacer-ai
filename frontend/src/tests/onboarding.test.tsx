import { describe, it, expect, vi } from 'vitest'

// Mock supabase before any module that imports it
vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn().mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } }),
    },
  },
}))

import {
  isOnboardingComplete,
  ONBOARDING_COMPLETION_MARKER,
} from '../screens/OnboardingScreen'

// ---------------------------------------------------------------------------
// Tests for isOnboardingComplete confirmation-gate detection.
//
// This locks the string-prefix detection so a copy change to the marker
// cannot silently break the post-onboarding redirect (D-02 / D-03).
// Both the runtime check and this test share ONBOARDING_COMPLETION_MARKER
// as a single source of truth.
// ---------------------------------------------------------------------------

describe('isOnboardingComplete', () => {
  it('returns true when message begins with the confirmation marker', () => {
    const msg = `${ONBOARDING_COMPLETION_MARKER} captured about you:\n\nGoals: General fitness...`
    expect(isOnboardingComplete(msg)).toBe(true)
  })

  it('returns true for the exact marker phrase from the system prompt', () => {
    expect(isOnboardingComplete('Here is what I have for you.')).toBe(true)
  })

  it('returns true when message has leading whitespace before the marker', () => {
    expect(isOnboardingComplete('  Here is what I have collected.')).toBe(true)
  })

  it('returns false for an ordinary mid-interview coach message', () => {
    expect(isOnboardingComplete('What days can you ride?')).toBe(false)
  })

  it('returns false for an empty string', () => {
    expect(isOnboardingComplete('')).toBe(false)
  })

  it('returns false when marker appears mid-sentence', () => {
    expect(
      isOnboardingComplete('Great, I will note that. Here is what I have so far.')
    ).toBe(false)
  })

  it('returns false for unrelated coaching messages', () => {
    expect(
      isOnboardingComplete('How many hours per week can you train?')
    ).toBe(false)
  })

  it('ONBOARDING_COMPLETION_MARKER matches the system prompt string exactly', () => {
    // The system prompt uses exactly "Here is what I have" (case-sensitive)
    expect(ONBOARDING_COMPLETION_MARKER).toBe('Here is what I have')
  })
})
