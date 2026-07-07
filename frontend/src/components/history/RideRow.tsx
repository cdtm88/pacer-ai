import { useState } from 'react'
import type { Ride } from '../../lib/api'

// ---------------------------------------------------------------------------
// RideRow — a single ride entry in the History list.
// Tap to expand for detailed power/HR summary and planned-vs-actual table.
//
// Compliance chip thresholds (PATTERNS.md lines 607-613):
//   compliance_pct >= 90  -> "XX% on target" in --color-good
//   compliance_pct < 90   -> "XX% on target" in --color-warn
//   compliance_pct null   -> "Unmatched" in --color-ink-3
// ---------------------------------------------------------------------------

interface RideRowProps {
  ride: Ride
}

function ComplianceChip({ pct }: { pct: number | null }) {
  if (pct === null || pct === undefined) {
    return (
      <span
        style={{
          fontSize: '13px',
          fontWeight: 500,
          color: 'var(--color-ink-3)',
        }}
      >
        Unmatched
      </span>
    )
  }

  const color = pct >= 90 ? 'var(--color-good)' : 'var(--color-warn)'
  return (
    <span
      style={{
        fontSize: '13px',
        fontWeight: 500,
        color,
      }}
    >
      {Math.round(pct)}% on target
    </span>
  )
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return '--'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function formatDate(isoDate: string): string {
  try {
    return new Date(isoDate).toLocaleDateString(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return isoDate
  }
}

export function RideRow({ ride }: RideRowProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      style={{
        borderBottom: '1px solid var(--color-line)',
      }}
    >
      {/* Collapsed row */}
      <button
        onClick={() => setExpanded((v) => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          padding: '12px 0',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
          gap: '12px',
        }}
        aria-expanded={expanded}
      >
        {/* Date */}
        <span
          style={{
            fontSize: '14px',
            fontWeight: 500,
            color: 'var(--color-ink)',
            flexShrink: 0,
            minWidth: '100px',
          }}
        >
          {formatDate(ride.ride_date)}
        </span>

        {/* Compliance chip */}
        <ComplianceChip pct={ride.compliance_pct ?? null} />

        {/* Stats */}
        <span
          style={{
            fontSize: '12px',
            color: 'var(--color-ink-2)',
            flexShrink: 0,
          }}
        >
          {ride.tss != null ? `TSS ${Math.round(ride.tss)}` : 'TSS --'}
        </span>
        <span
          style={{
            fontSize: '12px',
            color: 'var(--color-ink-2)',
            flexShrink: 0,
          }}
        >
          {formatDuration(ride.duration_secs ?? null)}
        </span>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div
          style={{
            padding: '0 0 16px 0',
          }}
        >
          {/* Power / HR summary */}
          <div
            style={{
              display: 'flex',
              gap: '24px',
              marginBottom: '12px',
              flexWrap: 'wrap',
            }}
          >
            {ride.np_watts != null && (
              <div>
                <div
                  style={{
                    fontSize: '12px',
                    color: 'var(--color-ink-3)',
                  }}
                >
                  Normalized Power
                </div>
                <div
                  style={{
                    fontSize: '15px',
                    fontWeight: 600,
                    color: 'var(--color-ink)',
                  }}
                >
                  {Math.round(ride.np_watts)} W
                </div>
              </div>
            )}
            {ride.avg_power != null && (
              <div>
                <div
                  style={{
                    fontSize: '12px',
                    color: 'var(--color-ink-3)',
                  }}
                >
                  Avg Power
                </div>
                <div
                  style={{
                    fontSize: '15px',
                    fontWeight: 600,
                    color: 'var(--color-ink)',
                  }}
                >
                  {Math.round(ride.avg_power)} W
                </div>
              </div>
            )}
            {ride.tss != null && (
              <div>
                <div
                  style={{
                    fontSize: '12px',
                    color: 'var(--color-ink-3)',
                  }}
                >
                  TSS
                </div>
                <div
                  style={{
                    fontSize: '15px',
                    fontWeight: 600,
                    color: 'var(--color-ink)',
                  }}
                >
                  {Math.round(ride.tss)}
                </div>
              </div>
            )}
            {ride.duration_secs != null && (
              <div>
                <div
                  style={{
                    fontSize: '12px',
                    color: 'var(--color-ink-3)',
                  }}
                >
                  Duration
                </div>
                <div
                  style={{
                    fontSize: '15px',
                    fontWeight: 600,
                    color: 'var(--color-ink)',
                  }}
                >
                  {formatDuration(ride.duration_secs)}
                </div>
              </div>
            )}
          </div>

          {/* Planned vs Actual table */}
          {ride.compliance_pct != null && (
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '13px',
                marginBottom: '8px',
              }}
            >
              <thead>
                <tr>
                  {['Metric', 'Planned', 'Actual', 'Delta'].map((h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: 'left',
                        padding: '4px 8px',
                        fontWeight: 600,
                        color: 'var(--color-ink-2)',
                        borderBottom: '1px solid var(--color-line)',
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td
                    style={{
                      padding: '4px 8px',
                      color: 'var(--color-ink-2)',
                    }}
                  >
                    Compliance
                  </td>
                  <td
                    style={{
                      padding: '4px 8px',
                      color: 'var(--color-ink-2)',
                    }}
                  >
                    100%
                  </td>
                  <td
                    style={{
                      padding: '4px 8px',
                      color: 'var(--color-ink)',
                    }}
                  >
                    {Math.round(ride.compliance_pct)}%
                  </td>
                  <td
                    style={{
                      padding: '4px 8px',
                      color:
                        ride.compliance_pct >= 90
                          ? 'var(--color-good)'
                          : 'var(--color-warn)',
                    }}
                  >
                    {ride.compliance_pct >= 100
                      ? '+0%'
                      : `-${Math.round(100 - ride.compliance_pct)}%`}
                  </td>
                </tr>
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
