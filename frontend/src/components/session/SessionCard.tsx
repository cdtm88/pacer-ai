import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { Play, Download, CheckCircle, XCircle, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { ZoneChip } from './ZoneChip'
import type { ZoneType } from './ZoneChip'
import { TsbChip } from './TsbChip'
import type { PmcRow } from './TsbChip'
import { markSessionDone, markSessionMissed } from '@/lib/api'

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
}

function formatDate(dateStr: string): { weekday: string; date: string } {
  const d = new Date(dateStr + 'T12:00:00')
  return {
    weekday: d.toLocaleDateString('en-US', { weekday: 'long' }),
    date: d.toLocaleDateString('en-US', { month: 'long', day: 'numeric' }),
  }
}

function getStructureText(structure: SessionData['structure']): string {
  if (!structure) return ''
  if (typeof structure === 'string') return structure
  return structure.text ?? ''
}

function getDuration(session: SessionData): number | null {
  return session.duration_minutes ?? session.duration_mins ?? null
}

function isValidZone(type: string | null): type is ZoneType {
  return ['recovery', 'endurance', 'tempo', 'threshold', 'vo2'].includes(type ?? '')
}

export function SessionCard({ session, pmc }: SessionCardProps) {
  const [missedOpen, setMissedOpen] = useState(false)
  const [isDoneLoading, setIsDoneLoading] = useState(false)
  const [isMissedLoading, setIsMissedLoading] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const { weekday, date } = formatDate(session.scheduled_date)
  const structureText = getStructureText(session.structure)
  const duration = getDuration(session)

  async function handleMarkDone() {
    setIsDoneLoading(true)
    try {
      await markSessionDone(session.id)
      queryClient.invalidateQueries({ queryKey: ['session', 'today'] })
      queryClient.invalidateQueries({ queryKey: ['sessions', 'upcoming'] })
    } finally {
      setIsDoneLoading(false)
    }
  }

  async function handleMarkMissed() {
    setIsMissedLoading(true)
    try {
      await markSessionMissed(session.id)
      queryClient.invalidateQueries({ queryKey: ['session', 'today'] })
      queryClient.invalidateQueries({ queryKey: ['sessions', 'upcoming'] })
    } finally {
      setIsMissedLoading(false)
      setMissedOpen(false)
    }
  }

  return (
    <>
      {/* Session card */}
      <div
        className="rounded-xl p-6"
        style={{
          backgroundColor: 'var(--color-surface)',
          border: '1px solid var(--color-line)',
          borderRadius: 12,
        }}
      >
        {/* Date line */}
        <p
          className="mb-2"
          style={{ fontSize: 14, fontWeight: 500, color: 'var(--color-ink-2)' }}
        >
          {weekday}, {date}
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
          {isValidZone(session.type) && <ZoneChip zone={session.type} />}
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

      {/* Action row */}
      <div className="grid grid-cols-2 gap-2 mt-4">
        {/* Start session */}
        <Button
          variant="default"
          className="col-span-2"
          style={{ backgroundColor: 'var(--color-blue-6)', color: '#fff' }}
          onClick={() => navigate('/session')}
        >
          <Play size={16} className="mr-2" />
          Start session
        </Button>

        {/* Export to Zwift (disabled, D-10) */}
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="w-full">
              <Button
                variant="outline"
                className="w-full"
                disabled
                aria-label="Export to Zwift"
              >
                <Download size={16} className="mr-2" />
                Export to Zwift
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent>Coming in the next update</TooltipContent>
        </Tooltip>

        {/* Mark done */}
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

        {/* Mark missed */}
        <Button
          variant="ghost"
          className="col-span-2"
          style={{ color: 'var(--color-bad)' }}
          onClick={() => setMissedOpen(true)}
        >
          <XCircle size={16} className="mr-2" />
          Mark missed
        </Button>
      </div>

      {/* Mark missed confirmation dialog */}
      <AlertDialog open={missedOpen} onOpenChange={setMissedOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Mark this session as missed?</AlertDialogTitle>
            <AlertDialogDescription>
              This will trigger a re-plan. Your coach will adjust upcoming sessions.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleMarkMissed}
              disabled={isMissedLoading}
              style={{ backgroundColor: 'var(--color-bad)', color: '#fff' }}
            >
              Yes, mark missed
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
