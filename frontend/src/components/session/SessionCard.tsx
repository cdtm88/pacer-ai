import { useState } from 'react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { Play, Download, CheckCircle, XCircle, Clock, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { StatTile } from '@/components/ui/StatTile'
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
} from '@/components/ui/alert-dialog'
import type { PmcRow } from './TsbChip'
import { ZwoExportModal } from './ZwoExportModal'
import { WorkoutProfileChart } from './WorkoutProfileChart'
import { markSessionDone, markSessionMissed } from '@/lib/api'
import { sessionTypeLabel, zoneColor, classifyTsb } from '@/lib/format'

// Tone-colored readiness chip styles keyed by classifyTsb().tone.
const FORM_TONE_STYLE: Record<'up' | 'flat' | 'down', { bg: string; text: string }> = {
  up:   { bg: 'color-mix(in srgb, var(--color-good) 15%, transparent)', text: 'var(--color-good)' },
  flat: { bg: 'var(--color-blue-0)', text: 'var(--color-blue-7)' },
  down: { bg: 'color-mix(in srgb, var(--color-amber) 15%, transparent)', text: 'var(--color-warn)' },
}

interface StructureSegment {
  duration_minutes?: number
  description?: string
}

export interface SessionData {
  id: string
  scheduled_date: string
  objective: string | null
  structure:
    | { text?: string; warmup?: StructureSegment; main_set?: StructureSegment; cooldown?: StructureSegment }
    | string
    | null
  type: string | null
  rpe_target: number | null
  duration_mins: number | null
  duration_minutes: number | null
  tss_target?: number | null
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

// Est. TSS is the raw tss_target the backend already prescribes for this session.
function getEstTss(session: SessionData): number | null {
  return session.tss_target ?? null
}

// IF is derived by inverting the planned-TSS formula (TSS = duration_hr * IF^2 * 100):
// IF = sqrt(tss_target / (duration_hr * 100)). No FTP required.
function getIntensityFactor(estTss: number | null, durationMin: number | null): number | null {
  if (estTss == null || durationMin == null || durationMin <= 0) return null
  const hours = durationMin / 60
  if (hours <= 0) return null
  return Math.round(Math.sqrt(estTss / (hours * 100)) * 100) / 100
}

export function SessionCard({ session, pmc, ftp = null }: SessionCardProps) {
  const [missedOpen, setMissedOpen] = useState(false)
  const [zwoOpen, setZwoOpen] = useState(false)
  const [isDoneLoading, setIsDoneLoading] = useState(false)
  const [isMissedLoading, setIsMissedLoading] = useState(false)
  const [logExpanded, setLogExpanded] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const structureText = getStructureText(session.structure)
  const duration = getDuration(session)
  const estTss = getEstTss(session)
  const intensityFactor = getIntensityFactor(estTss, duration)
  const accentColor = session.type ? zoneColor(session.type) : null
  // Readiness chip: only when the PMC series is display-ready (28+ days of data).
  const form = pmc && pmc.tss_display_ready ? classifyTsb(pmc.tsb) : null

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
        {accentColor && (
          <div style={{ height: 4, backgroundColor: accentColor }} />
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
            color: accentColor ?? 'var(--color-ink-3)',
          }}
        >
          {sessionTypeLabel(session.type)}
        </p>

        {/* Objective */}
        {session.objective && (
          <h2
            className="mb-2"
            style={{ fontSize: 28, fontWeight: 600, color: 'var(--color-ink)', lineHeight: 1.15 }}
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

        {/* Workout-structure profile (renders nothing for string / text-only structures);
            taller and centered as the Today-hub card centerpiece (D-6). */}
        <WorkoutProfileChart structure={session.structure} type={session.type} height={60} />

        {/* Stat tile row: duration / est TSS / IF. IF is derived from tss_target + duration,
            no FTP required; "--" renders when data is missing. */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          <StatTile
            label="Duration"
            value={duration != null ? duration : '--'}
            unit={duration != null ? 'min' : undefined}
          />
          <StatTile label="TSS" value={estTss != null ? Math.round(estTss) : '--'} />
          <StatTile label="IF" value={intensityFactor != null ? intensityFactor.toFixed(2) : '--'} />
        </div>

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
          {form && (
            <span
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5"
              style={{
                backgroundColor: FORM_TONE_STYLE[form.tone].bg,
                color: FORM_TONE_STYLE[form.tone].text,
                fontSize: 12,
                fontWeight: 500,
                lineHeight: 1.4,
              }}
            >
              <span style={{ opacity: 0.7 }}>Form:</span>
              {/* Label kept as its own text node (exact "Fresh"/"Balanced"/"Fatigued") for the test suite */}
              <span>{form.label}</span>
            </span>
          )}
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

      {/* Action stack: one primary (Start), one secondary (Export), then a quiet
          "log without riding" row for Mark done / Mark missed. All four buttons
          stay in the DOM with their accessible names for the test suite. */}
      <div className="flex flex-col gap-2 mt-4 md:mt-0">
        <Button
          variant="default"
          className="w-full"
          onClick={() => navigate('/session')}
        >
          <Play size={16} className="mr-2" />
          Start ride
        </Button>

        <Button
          variant="outline"
          className="w-full"
          aria-label="Export .zwo"
          onClick={() => setZwoOpen(true)}
        >
          <Download size={16} className="mr-2" />
          Export .zwo
        </Button>

        {/* Single quiet overflow affordance: collapses Mark done / Mark missed behind a
            "Log without riding" disclosure. Both actions stay mounted in the DOM (visually
            collapsed via max-height/opacity, not unmounted) so their accessible names remain
            queryable for the test suite regardless of expanded state. */}
        <button
          type="button"
          className="mt-1 pt-3 flex items-center gap-1 w-full text-left"
          style={{
            borderTop: '1px solid var(--color-line)',
            background: 'transparent',
            border: 'none',
            borderTopWidth: 1,
            borderTopStyle: 'solid',
            borderTopColor: 'var(--color-line)',
            cursor: 'pointer',
          }}
          onClick={() => setLogExpanded((v) => !v)}
          aria-expanded={logExpanded}
          aria-controls="log-without-riding-actions"
        >
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              color: 'var(--color-ink-3)',
            }}
          >
            Log without riding
          </span>
          <ChevronDown
            size={14}
            style={{
              color: 'var(--color-ink-3)',
              transform: logExpanded ? 'rotate(180deg)' : undefined,
              transition: 'transform 150ms',
            }}
          />
        </button>
        <div
          id="log-without-riding-actions"
          className="flex gap-2"
          inert={!logExpanded ? true : undefined}
          style={
            logExpanded
              ? { marginTop: 8 }
              : { maxHeight: 0, overflow: 'hidden', opacity: 0, marginTop: 0, pointerEvents: 'none' }
          }
        >
          <Button
            variant="ghost"
            size="sm"
            className="flex-1"
            style={{ color: 'var(--color-ink-2)' }}
            onClick={handleMarkDone}
            disabled={isDoneLoading}
          >
            <CheckCircle size={15} className="mr-1.5" />
            Mark done
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="flex-1"
            style={{ color: 'var(--color-ink-2)' }}
            onClick={() => setMissedOpen(true)}
          >
            <XCircle size={15} className="mr-1.5" />
            Mark missed
          </Button>
        </div>
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
