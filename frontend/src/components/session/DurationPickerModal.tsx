import { useState } from 'react'
import { useNavigate } from 'react-router'
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from '@/components/ui/alert-dialog'
import { useUiStore } from '@/stores/uiStore'

const PRESETS = [30, 45, 60]

interface DurationPickerModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function DurationPickerModal({ open, onOpenChange }: DurationPickerModalProps) {
  const navigate = useNavigate()
  const [selected, setSelected] = useState<number | null>(null)
  const [custom, setCustom] = useState('')
  const [customError, setCustomError] = useState('')

  function handlePreset(mins: number) {
    setSelected(mins)
    setCustom('')
    setCustomError('')
  }

  function handleCustomChange(val: string) {
    setSelected(null)
    setCustom(val)
    setCustomError('')
  }

  function validateCustom(): number | null {
    const n = parseInt(custom, 10)
    if (!custom.trim() || isNaN(n) || !Number.isInteger(n)) return null
    if (n < 10 || n > 180) return null
    return n
  }

  function isValid(): boolean {
    if (selected !== null) return true
    const n = validateCustom()
    if (custom.trim() && n === null) return false
    return n !== null
  }

  function handleSubmit() {
    const chosen = selected ?? validateCustom()
    if (chosen === null) {
      setCustomError('Enter a time between 10 and 180 minutes')
      return
    }
    useUiStore.getState().setFreeRideDurationMins(chosen)
    onOpenChange(false)
    navigate('/session')
  }

  function handleCustomBlur() {
    if (custom.trim()) {
      const n = validateCustom()
      if (n === null) {
        setCustomError('Enter a time between 10 and 180 minutes')
      }
    }
  }

  function handleOpenChange(val: boolean) {
    if (!val) {
      setSelected(null)
      setCustom('')
      setCustomError('')
    }
    onOpenChange(val)
  }

  const customValid = custom.trim() ? validateCustom() !== null : true

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent
        style={{
          backgroundColor: 'var(--color-surface)',
          border: '1px solid var(--color-line)',
          borderRadius: 16,
          padding: 24,
          maxWidth: 400,
        }}
      >
        <AlertDialogHeader>
          <AlertDialogTitle
            style={{
              fontSize: 20,
              fontWeight: 600,
              color: 'var(--color-ink)',
              marginBottom: 16,
            }}
          >
            How long will you ride?
          </AlertDialogTitle>
        </AlertDialogHeader>

        {/* Preset buttons */}
        <div
          style={{
            display: 'flex',
            gap: 8,
            marginBottom: 16,
          }}
        >
          {PRESETS.map(mins => {
            const isActive = selected === mins
            return (
              <button
                key={mins}
                onClick={() => handlePreset(mins)}
                style={{
                  flex: 1,
                  padding: '10px 0',
                  borderRadius: 8,
                  border: `1px solid ${isActive ? 'var(--color-blue-6)' : 'var(--color-line)'}`,
                  backgroundColor: isActive ? 'var(--color-blue-6)' : 'transparent',
                  color: isActive ? '#fff' : 'var(--color-ink)',
                  fontWeight: isActive ? 600 : 400,
                  fontSize: 14,
                  cursor: 'pointer',
                }}
              >
                {mins} min
              </button>
            )
          })}
        </div>

        {/* Custom input */}
        <div style={{ marginBottom: 8 }}>
          <label
            style={{
              display: 'block',
              fontSize: 13,
              color: 'var(--color-ink-2)',
              marginBottom: 6,
              fontWeight: 500,
            }}
          >
            Custom
          </label>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <input
              type="number"
              min={10}
              max={180}
              value={custom}
              onChange={e => handleCustomChange(e.target.value)}
              onBlur={handleCustomBlur}
              placeholder="e.g. 75"
              style={{
                width: '100%',
                padding: '10px 44px 10px 12px',
                borderRadius: 8,
                border: `1px solid ${customError ? 'var(--color-bad)' : 'var(--color-line)'}`,
                backgroundColor: 'var(--color-surface)',
                color: 'var(--color-ink)',
                fontSize: 14,
                outline: 'none',
              }}
            />
            <span
              style={{
                position: 'absolute',
                right: 12,
                fontSize: 14,
                color: 'var(--color-ink-2)',
                pointerEvents: 'none',
              }}
            >
              min
            </span>
          </div>
          {customError && (
            <p
              style={{
                fontSize: 12,
                color: 'var(--color-bad)',
                marginTop: 4,
              }}
            >
              {customError}
            </p>
          )}
        </div>

        <AlertDialogFooter style={{ marginTop: 20, gap: 8 }}>
          <AlertDialogCancel
            style={{
              color: 'var(--color-ink-2)',
              border: '1px solid var(--color-line)',
              backgroundColor: 'transparent',
              borderRadius: 8,
              padding: '10px 16px',
              fontSize: 14,
              cursor: 'pointer',
            }}
          >
            Never mind
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={e => {
              e.preventDefault()
              if (!isValid() || !customValid) {
                setCustomError('Enter a time between 10 and 180 minutes')
                return
              }
              handleSubmit()
            }}
            disabled={!isValid() || !customValid}
            style={{
              backgroundColor: isValid() && customValid ? 'var(--color-blue-6)' : 'var(--color-line)',
              color: isValid() && customValid ? '#fff' : 'var(--color-ink-3)',
              border: 'none',
              borderRadius: 8,
              padding: '10px 20px',
              fontSize: 14,
              fontWeight: 600,
              cursor: isValid() && customValid ? 'pointer' : 'not-allowed',
            }}
          >
            Start session
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
