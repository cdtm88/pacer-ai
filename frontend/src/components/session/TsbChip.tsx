// TsbChip: renders a fresh/balanced/fatigued pill gated on tss_display_ready (D-14).
// Returns null when tss_display_ready is false — no placeholder, no empty space.

export interface PmcRow {
  tss_display_ready: boolean
  ctl: number
  atl: number
  tsb: number
  date: string
}

// Thresholds documented inline per spec:
// fresh:    tsb > 5  (clearly positive fitness buffer)
// fatigued: tsb < -10 (accumulated fatigue)
// balanced: anything in between
function classifyTsb(tsb: number): 'fresh' | 'balanced' | 'fatigued' {
  if (tsb > 5) return 'fresh'
  if (tsb < -10) return 'fatigued'
  return 'balanced'
}

const STATE_STYLE: Record<'fresh' | 'balanced' | 'fatigued', { bg: string; text: string; label: string }> = {
  fresh: {
    bg:    'color-mix(in srgb, var(--color-good) 15%, transparent)',
    text:  'var(--color-good)',
    label: 'Fresh',
  },
  balanced: {
    bg:    'var(--color-blue-0)',
    text:  'var(--color-blue-7)',
    label: 'Balanced',
  },
  fatigued: {
    bg:    'color-mix(in srgb, var(--color-amber) 15%, transparent)',
    text:  'var(--color-warn)',
    label: 'Fatigued',
  },
}

interface TsbChipProps {
  pmc: PmcRow | null | undefined
}

export function TsbChip({ pmc }: TsbChipProps) {
  // Gate: only show when 28+ days of data (tss_display_ready)
  if (!pmc || !pmc.tss_display_ready) return null

  const state = classifyTsb(pmc.tsb)
  const { bg, text, label } = STATE_STYLE[state]

  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5"
      style={{
        backgroundColor: bg,
        color: text,
        fontSize: 12,
        fontWeight: 500,
        lineHeight: 1.4,
      }}
    >
      {label}
    </span>
  )
}
