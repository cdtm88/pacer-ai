import { useState } from 'react'

// PromptChip: pill button used for suggested prompts / quick replies.
// Extracted from the byte-identical local copies duplicated in ChatScreen.tsx
// and OnboardingScreen.tsx (D-8 component unification). Hover handled inline
// to match the inline-style convention used throughout these chat screens.
export function PromptChip({
  label,
  onClick,
  disabled,
}: {
  label: string
  onClick: () => void
  disabled?: boolean
}) {
  const [hover, setHover] = useState(false)
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        padding: '8px 14px',
        borderRadius: '999px',
        border: '1px solid var(--color-line)',
        backgroundColor: hover && !disabled ? 'var(--color-bg-2)' : 'var(--color-surface)',
        color: 'var(--color-ink-2)',
        fontSize: '14px',
        fontFamily: 'var(--font-family-sans)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.6 : 1,
        transition: 'background-color 0.15s',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </button>
  )
}
