import { describe, it, expect } from 'vitest'
import { triggerLabel, formatDate } from '@/lib/format'

// Format helpers for the Adaptations log UI (Phase 13 gap closure).
// triggerLabel humanizes the DB `trigger` enum (D-09); formatDate is the
// shared date formatter extracted from RideRow so both surfaces render
// byte-identical date strings.

describe('lib/format — triggerLabel', () => {
  it("maps 'missed' to 'Missed session'", () => {
    expect(triggerLabel('missed')).toBe('Missed session')
  })

  it("maps 'underperformance' to 'Underperformance'", () => {
    expect(triggerLabel('underperformance')).toBe('Underperformance')
  })

  it("maps 'overreaching' to 'Overreaching'", () => {
    expect(triggerLabel('overreaching')).toBe('Overreaching')
  })

  it('falls back to titleCase for an unrecognized value without throwing', () => {
    expect(triggerLabel('some_new_value')).toBe('Some_new_value')
  })

  it("defaults to 'Adaptation' for null/undefined", () => {
    expect(triggerLabel(null)).toBe('Adaptation')
    expect(triggerLabel(undefined)).toBe('Adaptation')
  })
})

describe('lib/format — formatDate', () => {
  it('formats an ISO date as a short weekday, month, day string', () => {
    const result = formatDate('2026-07-06T12:00:00Z')
    expect(result).toMatch(/Jul/)
    expect(result).toMatch(/6/)
    expect(result).toMatch(/[A-Za-z]{3},/) // short weekday followed by comma
  })

  it('returns the raw input on an unparseable date, without throwing', () => {
    expect(formatDate('not-a-date')).toBe('not-a-date')
  })
})
