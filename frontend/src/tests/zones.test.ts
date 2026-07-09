import { describe, it, expect } from 'vitest'
import { ZONE_META, zoneColor, zoneLabel, type ZoneKey } from '@/lib/zones'

// Drift-guard smoke test: locks the single canonical zone map (D-8) against
// silent divergence between screens. If this test fails after a refactor,
// something re-introduced a local zone-map duplicate instead of importing
// from lib/zones.

describe('lib/zones — canonical zone map', () => {
  it('has exactly the 5 expected zone keys', () => {
    const keys = Object.keys(ZONE_META).sort()
    expect(keys).toEqual(['endurance', 'recovery', 'tempo', 'threshold', 'vo2'])
  })

  it('maps each zone color to the matching CSS token', () => {
    expect(ZONE_META.recovery.color).toBe('var(--color-zone-recovery)')
    expect(ZONE_META.endurance.color).toBe('var(--color-zone-endurance)')
    expect(ZONE_META.tempo.color).toBe('var(--color-zone-tempo)')
    expect(ZONE_META.threshold.color).toBe('var(--color-zone-threshold)')
    expect(ZONE_META.vo2.color).toBe('var(--color-zone-vo2)')
  })

  it('maps each zone to its canonical label', () => {
    expect(ZONE_META.recovery.label).toBe('Recovery')
    expect(ZONE_META.endurance.label).toBe('Endurance')
    expect(ZONE_META.tempo.label).toBe('Tempo')
    expect(ZONE_META.threshold.label).toBe('Threshold')
    expect(ZONE_META.vo2.label).toBe('VO2 Max')
  })

  it('has the correct percent ranges, with vo2 pctHigh strictly null (open-ended)', () => {
    expect(ZONE_META.recovery).toMatchObject({ pctLow: 0, pctHigh: 55 })
    expect(ZONE_META.endurance).toMatchObject({ pctLow: 56, pctHigh: 75 })
    expect(ZONE_META.tempo).toMatchObject({ pctLow: 76, pctHigh: 90 })
    expect(ZONE_META.threshold).toMatchObject({ pctLow: 91, pctHigh: 105 })
    expect(ZONE_META.vo2.pctLow).toBe(106)
    expect(ZONE_META.vo2.pctHigh).toBeNull()
  })

  it('zoneColor returns the token for a known zone and falls back for null/unknown', () => {
    expect(zoneColor('threshold')).toBe('var(--color-zone-threshold)')
    expect(zoneColor(null)).toBe('var(--color-ink-3)')
    expect(zoneColor('bogus')).toBe('var(--color-ink-3)')
  })

  it('zoneLabel returns the canonical label for a known zone and empty string for null', () => {
    expect(zoneLabel('vo2')).toBe('VO2 Max')
    expect(zoneLabel(null)).toBe('')
  })

  it('exposes a ZoneKey type usable as a type-only import', () => {
    const key: ZoneKey = 'threshold'
    expect(ZONE_META[key]).toBeDefined()
  })
})
