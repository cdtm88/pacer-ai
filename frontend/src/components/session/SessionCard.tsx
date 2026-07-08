import { useState } from 'react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { Play, Download, CheckCircle, XCircle, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
} from '@/components/ui/alert-dialog'
import { TsbChip } from './TsbChip'
import type { PmcRow } from './TsbChip'
import { ZwoExportModal } from './ZwoExportModal'
import { markSessionDone, markSessionMissed } from '@/lib/api'
import { sessionTypeLabel } from '@/lib/format'

const ZONE_COLORS: Record<string, string> = {
  recovery:  '#2B8A5B',
  endurance: '#228BE6',
  tempo:     '#F0A030',
  threshold: '#E8590C',
  vo2:       '#C92A2A',
}

export interface SessionData {
  id: string
  scheduled_date: string
  objective: string | null
  structure: { text?: string } | string | null
  type: string | null
  rpe_target: number | null
  duration_mins: number | null
  duration_minutes: number | null
}

interface SessionCardProps {
  session: SessionData
  pmc: PmcRow | null | undefined
  ftp?: number | null
}

function getStructureText(structure: SessionData['structure']): string {
  if (!structure) return ''
  if (typeof structure === 'string') return structure
  return structure.text ?? ''
}

function getDuration(session: SessionData): number | null {
  return session.duration_minutes ?? session.duration_mins ?? null
}

export function SessionCard({ session, pmc, ftp = null }: SessionCardProps) {
  const [missedOpen, setMissedOpen] = useState(false)
  const [zwoOpen, setZwoOpen] = useState(false)
  const [isDoneLoading, setIsDoneLoading] = useState(false)
  const [isMissedLoading, setIsMissedLoading] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const structureText = getStructureText(session.structure)
  const duration = getDuration(session)
  const zoneColor = session.type ? (ZONE_COLORS[session.type] ?? null) : null

  async function handleMarkDone() {
    setIsDoneLoading(true)
    try {
      await markSessionDone(session.id)
      // Keys match TodayScreen useQuery keys: ['session','today'] and ['sessions','upcoming']
      queryClient.invalidateQueries({ queryKey: ['session', 'today'] })
      queryClient.invalidateQueries({ queryKey: ['sessions', 'upcoming'] })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not mark session as done. Please try again.')
    } finally {
      setIsDoneLoading(false)
    }
  }

  async function handleMarkMissed() {
    setIsMissedLoading(true)
    try {
      await markSessionMissed(session.id)
      setMissedOpen(false) // close confirmation only on success; stays open on failure for retry
      // Keys match TodayScreen useQuery keys: ['session','today'] and ['sessions','upcoming']
      queryClient.invalidateQueries({ queryKey: ['session', 'today'] })
      queryClient.invalidateQueries({ queryKey: ['sessions', 'upcoming'] })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not mark session as missed. Please try again.')
    } finally {
      setIsMissedLoading(false)
    }
  }

  return (
    <>
      {/* Card + actions: stacked on mobile, side-by-side on desktop */}
      <div className="md:grid md:grid-cols-[1fr_220px] md:gap-6 md:items-start">
      {/* Session card */}
      <div
        className="rounded-xl overflow-hidden"
        style={{
          backgroundColor: 'var(--color-surface)',
          border: '1px solid var(--color-line)',
          borderRadius: 12,
        }}
      >
        {/* Zone color accent bar */}
        {zoneColor && (
          <div style={{ height: 4, backgroundColor: zoneColor }} />
        )}
        <div className="p-6">
        {/* Session type eyebrow (zone-colored) */}
        <p
          className="mb-1.5"
          style={{
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: zoneColor ?? 'var(--color-ink-3)',
          }}
        >
          {sessionTypeLabel(session.type)}
        </p>

        {/* Objective */}
        {session.objective && (
          <h2
            className="mb-2"
            style={{ fontSize: 20, fontWeight: 600, color: 'var(--color-ink)', lineHeight: 1.2 }}
          >
            {session.objective}
          </h2>
        )}

        {/* Structure */}
        {structureText && (
          <p
            className="mb-3"
            style={{ fontSize: 16, color: 'var(--color-ink-2)', lineHeight: 1.5 }}
          >
            {structureText}
          </p>
        )}

        {/* Targets chip row */}
        <div className="flex flex-wrap gap-2 mb-3">
          {session.rpe_target != null && (
            <span
              className="inline-flex items-center rounded-full px-2 py-0.5"
              style={{
                backgroundColor: 'var(--color-bg-2)',
                color: 'var(--color-ink-2)',
                fontSize: 12,
                fontWeight: 500,
              }}
            >
              RPE {session.rpe_target}
            </span>
          )}
          <TsbChip pmc={pmc} />
        </div>

        {/* Duration */}
        {duration != null && (
          <div
            className="flex items-center gap-1.5"
            style={{ fontSize: 14, color: 'var(--color-ink-2)' }}
          >
            <Clock size={16} />
            <span>{duration} min</span>
          </div>
        )}
        </div>
      </div>

      {/* Action row — always renders all four buttons; Mark missed opens the AlertDialog */}
      <div className="flex flex-col gap-2 mt-4 md:mt-0">
        <Button
          variant="default"
          className="w-full"
          style={{ backgroundColor: 'var(--color-blue-6)', color: '#fff' }}
          onClick={() => navigate('/session')}
        >
          <Play size={16} className="mr-2" />
          Start session
        </Button>

        <Button
          variant="outline"
          className="w-full"
          aria-label="Export to Zwift"
          onClick={() => setZwoOpen(true)}
        >
          <Download size={16} className="mr-2" />
          Export to Zwift
        </Button>

        <Button
          variant="outline"
          className="w-full"
          style={{ color: 'var(--color-good)', borderColor: 'var(--color-good)' }}
          onClick={handleMarkDone}
          disabled={isDoneLoading}
        >
          <CheckCircle size={16} className="mr-2" />
          Mark done
        </Button>

        <Button
          variant="ghost"
          className="w-full"
          style={{ color: 'var(--color-bad)' }}
          onClick={() => setMissedOpen(true)}
        >
          <XCircle size={16} className="mr-2" />
          Mark missed
        </Button>
      </div>

      {/* Controlled AlertDialog for Mark Missed — open driven by missedOpen state, no Trigger used.
          Confirm uses a plain Button (not AlertDialogAction) so auto-close is suppressed;
          closing is owned solely by handleMarkMissed's success path, keeping dialog open on failure for retry. */}
      <AlertDialog open={missedOpen} onOpenChange={setMissedOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Mark this session as missed?</AlertDialogTitle>
            <AlertDialogDescription>
              This will trigger a re-plan. Your coach will adjust upcoming sessions.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setMissedOpen(false)}>Keep it</AlertDialogCancel>
            <Button
              style={{ backgroundColor: 'var(--color-bad)', color: '#fff' }}
              onClick={handleMarkMissed}
              disabled={isMissedLoading}
            >
              Yes, mark missed
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      </div>{/* end card+actions grid */}

      {/* ZWO export panel (inline, no portal) */}
      {zwoOpen && (
        <ZwoExportModal
          session={session}
          ftp={ftp}
          onClose={() => setZwoOpen(false)}
        />
      )}
    </>
  )
}
