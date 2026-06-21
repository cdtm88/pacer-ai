import { useState } from 'react'
import { toast } from 'sonner'
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { exportSessionZwo } from '@/lib/api'
import type { SessionData } from './SessionCard'

interface ZwoExportModalProps {
  session: SessionData
  ftp: number | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ZwoExportModal({ session, ftp, open, onOpenChange }: ZwoExportModalProps) {
  const [downloading, setDownloading] = useState(false)

  // Derive structured segments from session.structure (may be null, string, or SessionStructure object)
  const structure =
    session.structure && typeof session.structure === 'object' && !('text' in session.structure)
      ? (session.structure as { warmup?: { duration_minutes: number }; main_set?: { duration_minutes: number }; cooldown?: { duration_minutes: number } })
      : null

  async function handleDownload() {
    setDownloading(true)
    try {
      await exportSessionZwo(session.id)
      toast.success('Workout file downloaded.')
      onOpenChange(false)
    } catch (err) {
      const message = err instanceof Error ? err.message : ''
      if (message.includes('session_not_found')) {
        toast.error('Session not found. Refresh the page and try again.')
      } else {
        toast.error('Export failed. Try again or contact support if the problem continues.')
      }
      // Do NOT call onOpenChange(false) here - modal stays open for retry (D-07)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Export to Zwift</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div>
              {/* Session name line: type - scheduled_date with spaced hyphen (no em dash) */}
              <p
                className="mb-1"
                style={{ fontWeight: 500, color: 'var(--color-ink)' }}
              >
                {session.type} - {session.scheduled_date}
              </p>

              {/* FTP line */}
              <p
                className="mb-3"
                style={{ fontSize: 14, color: 'var(--color-ink-2)' }}
              >
                {ftp != null
                  ? `FTP used: ${ftp}W`
                  : 'FTP used: 100W (assumed - no estimate yet)'}
              </p>

              {/* Workout summary */}
              <p
                className="mb-1"
                style={{ fontWeight: 500, color: 'var(--color-ink)' }}
              >
                Workout
              </p>
              <ul style={{ fontSize: 14, color: 'var(--color-ink-2)' }}>
                {structure?.warmup && (
                  <li>Warmup - {structure.warmup.duration_minutes} min</li>
                )}
                {structure?.main_set && (
                  <li>Main set - {structure.main_set.duration_minutes} min</li>
                )}
                {structure?.cooldown && (
                  <li>Cool-down - {structure.cooldown.duration_minutes} min</li>
                )}
              </ul>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>

        <AlertDialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Close
          </Button>
          <Button
            style={{ backgroundColor: 'var(--color-blue-6)', color: '#fff' }}
            onClick={handleDownload}
            disabled={downloading}
          >
            Download .zwo
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
