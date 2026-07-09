import { useParams, Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getRides, getRideStream } from '../lib/api'
import { RideChart } from '../components/rides/RideChart'

// ---------------------------------------------------------------------------
// AnalysisScreen — the per-ride deep-dive (RIDE-10).
//
// Resolves the ride to show from either the route param (/rides/:rideId) or,
// when visiting the default /analysis route, the most recent ride from the
// already-fetched rides list (no new backend endpoint, per 11-RESEARCH.md
// Don't Hand-Roll: "latest ride" lookup).
// ---------------------------------------------------------------------------

export function AnalysisScreen() {
  const { rideId: routeRideId } = useParams()
  const ridesQuery = useQuery({ queryKey: ['rides'], queryFn: getRides })
  const rideId = routeRideId ?? ridesQuery.data?.[0]?.id
  const streamQuery = useQuery({
    queryKey: ['ride-stream', rideId],
    queryFn: () => getRideStream(rideId!),
    enabled: !!rideId,
    staleTime: Infinity,
  })

  const isLoading = ridesQuery.isLoading || (!!rideId && streamQuery.isLoading)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center" style={{ minHeight: '60vh' }}>
        <div
          className="w-8 h-8 rounded-full border-2 border-t-transparent animate-spin"
          style={{ borderColor: 'var(--color-blue-6)', borderTopColor: 'transparent' }}
          aria-label="Loading"
        />
      </div>
    )
  }

  // Empty: no rides at all for this user, and no explicit rideId was routed to.
  if (!routeRideId && !ridesQuery.isLoading && !ridesQuery.isError && !rideId) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 24 }}>
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
          Upload a .FIT file to see your ride analysis.
        </p>
      </div>
    )
  }

  if (streamQuery.isError) {
    const message = streamQuery.error instanceof Error ? streamQuery.error.message : ''

    // getRideStream throws Error(`getRideStream failed: <status>`).
    if (message.includes('404')) {
      return (
        <div style={{ textAlign: 'center', paddingTop: 24 }}>
          <p style={{ fontSize: '15px', color: 'var(--color-ink-2)', margin: '0 0 8px' }}>
            This ride couldn&apos;t be found.
          </p>
          <Link
            to="/progress"
            style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-brand)' }}
          >
            Back to ride log
          </Link>
        </div>
      )
    }

    if (message.includes('422')) {
      return (
        <div style={{ textAlign: 'center', paddingTop: 24 }}>
          <p style={{ fontSize: '15px', color: 'var(--color-ink-2)', margin: 0, lineHeight: '1.5' }}>
            Could not read this ride file. It may be damaged or in an unsupported format.
          </p>
        </div>
      )
    }

    return (
      <button
        onClick={() => streamQuery.refetch()}
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
        Could not load ride data. Tap to retry.
      </button>
    )
  }

  return (
    <div
      style={{
        width: '100%',
        maxWidth: 720,
        margin: '0 auto',
        padding: '20px 20px 40px',
      }}
    >
      {streamQuery.data && <RideChart stream={streamQuery.data} />}
    </div>
  )
}
