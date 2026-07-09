import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { exportSessionZwo } from '@/lib/api'
import type { SessionData } from './SessionCard'

interface ZwoExportPanelProps {
  session: SessionData
  ftp: number | null
  onClose: () => void
}

export function ZwoExportModal({ session, ftp, onClose }: ZwoExportPanelProps) {
  const [downloading, setDownloading] = useState(false)

  const structure =
    session.structure && typeof session.structure === 'object' && !('text' in session.structure)
      ? (session.structure as {
          warmup?: { duration_minutes: number }
          main_set?: { duration_minutes: number }
          cooldown?: { duration_minutes: number }
        })
      : null

  async function handleDownload() {
    setDownloading(true)
    try {
      await exportSessionZwo(session.id)
      toast.success('Workout file downloaded.')
      onClose()
    } catch (err) {
      const message = err instanceof Error ? err.message : ''
      if (message.includes('session_not_found')) {
        toast.error('Session not found. Refresh the page and try again.')
      } else {
        toast.error('Export failed. Try again or contact support if the problem continues.')
      }
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div
      className="rounded-xl p-5 mt-2"
      style={{
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-line)',
      }}
    >
      <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-ink)', marginBottom: 4 }}>
        Export .zwo
      </p>
      <p style={{ fontSize: 14, fontWeight: 500, color: 'var(--color-ink)', marginBottom: 2 }}>
        {session.type} - {session.scheduled_date}
      </p>
      <p style={{ fontSize: 13, color: 'var(--color-ink-2)', marginBottom: 12 }}>
        {ftp != null ? `FTP used: ${ftp}W` : 'FTP: not yet estimated — free-ride format'}
      </p>

      {structure && (
        <>
          <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-ink)', marginBottom: 4 }}>
            Workout
          </p>
          <ul style={{ fontSize: 13, color: 'var(--color-ink-2)', marginBottom: 12, paddingLeft: 16 }}>
            {structure.warmup && <li>Warmup - {structure.warmup.duration_minutes} min</li>}
            {structure.main_set && <li>Main set - {structure.main_set.duration_minutes} min</li>}
            {structure.cooldown && <li>Cool-down - {structure.cooldown.duration_minutes} min</li>}
          </ul>
        </>
      )}

      <div className="flex flex-col gap-2">
        <Button
          className="w-full"
          style={{ backgroundColor: 'var(--color-blue-6)', color: '#fff' }}
          onClick={handleDownload}
          disabled={downloading}
        >
          Download .zwo
        </Button>
        <Button variant="outline" className="w-full" onClick={onClose}>
          Close
        </Button>
      </div>
    </div>
  )
}
