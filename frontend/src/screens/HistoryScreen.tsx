import { useQuery } from '@tanstack/react-query'
import { getRides, getPmcHistory } from '../lib/api'
import { FitUploadZone } from '../components/history/FitUploadZone'
import { RideRow } from '../components/history/RideRow'
import { CtlSparkline } from '../components/history/CtlSparkline'

// ---------------------------------------------------------------------------
// HistoryScreen — FIT upload, gated CTL sparkline, and ride list.
//
// Layout:
//   1. FitUploadZone — always pinned at top
//   2. CtlSparkline — shown only when tss_display_ready (D-14)
//   3. Ride list — RideRows with compliance, TSS, duration
//
// Empty state when no rides: "No rides yet" heading + upload prompt.
// Error state: inline retry message.
// ---------------------------------------------------------------------------

function SkeletonRow() {
  return (
    <div
      style={{
        height: '52px',
        borderRadius: '6px',
        backgroundColor: 'var(--color-line-2)',
        marginBottom: '8px',
        animation: 'pulse 1.5s ease-in-out infinite',
      }}
    />
  )
}

export function HistoryScreen() {
  const ridesQuery = useQuery({
    queryKey: ['rides'],
    queryFn: getRides,
  })

  const pmcQuery = useQuery({
    queryKey: ['pmc-history'],
    queryFn: getPmcHistory,
  })

  const rides = ridesQuery.data ?? []
  const pmcHistory = pmcQuery.data ?? []

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: 'var(--color-bg)',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '16px 16px 0',
        }}
      >
        <h1
          style={{
            fontSize: '20px',
            fontWeight: 600,
            color: 'var(--color-ink)',
            margin: '0 0 12px',
          }}
        >
          History
        </h1>

        {/* FIT upload zone: always visible */}
        <FitUploadZone />

        {/* CTL sparkline: gated on tss_display_ready (D-14) */}
        {!pmcQuery.isLoading && pmcHistory.length > 0 && (
          <div style={{ marginTop: '12px' }}>
            <CtlSparkline history={pmcHistory} />
          </div>
        )}
      </div>

      {/* Ride list */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px 16px 32px',
        }}
      >
        {ridesQuery.isLoading && (
          <>
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </>
        )}

        {ridesQuery.isError && (
          <button
            onClick={() => ridesQuery.refetch()}
            style={{
              display: 'block',
              width: '100%',
              padding: '12px',
              textAlign: 'center',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--color-bad)',
              fontSize: '14px',
            }}
          >
            Could not load history. Tap to retry.
          </button>
        )}

        {!ridesQuery.isLoading && !ridesQuery.isError && rides.length === 0 && (
          <div
            style={{
              textAlign: 'center',
              paddingTop: '40px',
            }}
          >
            <h2
              style={{
                fontSize: '18px',
                fontWeight: 600,
                color: 'var(--color-ink)',
                margin: '0 0 8px',
              }}
            >
              No rides yet
            </h2>
            <p
              style={{
                fontSize: '15px',
                color: 'var(--color-ink-2)',
                margin: 0,
                lineHeight: '1.5',
              }}
            >
              Upload a .FIT file from Zwift or your head unit to see your history.
            </p>
          </div>
        )}

        {!ridesQuery.isLoading &&
          !ridesQuery.isError &&
          rides.map((ride) => <RideRow key={ride.id} ride={ride} />)}
      </div>
    </div>
  )
}
