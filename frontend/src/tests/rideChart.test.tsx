import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RideChart } from '../components/rides/RideChart'
import type { RideStream } from '../lib/api'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeStream(overrides: Partial<RideStream> = {}): RideStream {
  return {
    series: [
      { t: 0, power: 150, heart_rate: 120, cadence: 80, speed: 8.5, altitude: 100, distance: 0 },
      { t: 60, power: 180, heart_rate: 135, cadence: 85, speed: 9.0, altitude: 105, distance: 500 },
      { t: 120, power: 160, heart_rate: 130, cadence: 82, speed: 8.8, altitude: 102, distance: 1000 },
    ],
    channels: {
      power: true,
      heart_rate: true,
      cadence: true,
      speed: true,
      altitude: true,
      distance: true,
    },
    laps: [60],
    hr_zone_distribution: null,
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('RideChart', () => {
  it('renders no elevation card when altitude absent', () => {
    const stream = makeStream({
      channels: {
        power: true,
        heart_rate: true,
        cadence: false,
        speed: false,
        altitude: false,
        distance: true,
      },
    })
    render(<RideChart stream={stream} />)
    expect(screen.queryByText('Elevation')).not.toBeInTheDocument()
    expect(screen.getByText('Power')).toBeInTheDocument()
    expect(screen.getByText('Heart rate')).toBeInTheDocument()
  })

  it('renders one card per present channel', () => {
    const stream = makeStream({
      channels: {
        power: true,
        heart_rate: true,
        cadence: false,
        speed: false,
        altitude: false,
        distance: false,
      },
    })
    render(<RideChart stream={stream} />)
    expect(screen.getByText('Power')).toBeInTheDocument()
    expect(screen.getByText('Heart rate')).toBeInTheDocument()
    expect(screen.queryByText('Cadence')).not.toBeInTheDocument()
    expect(screen.queryByText('Speed')).not.toBeInTheDocument()
    expect(screen.queryByText('Elevation')).not.toBeInTheDocument()
  })

  it('hides time-in-zone section when distribution null', () => {
    const stream = makeStream({ hr_zone_distribution: null })
    render(<RideChart stream={stream} />)
    expect(screen.queryByText('Time in zone')).not.toBeInTheDocument()
  })

  it('shows time-in-zone rows when distribution present', () => {
    const stream = makeStream({
      hr_zone_distribution: [
        { zone: 1, name: 'Recovery', seconds: 300, pct: 25 },
        { zone: 2, name: 'Endurance', seconds: 400, pct: 33 },
        { zone: 3, name: 'Tempo', seconds: 200, pct: 17 },
        { zone: 4, name: 'Threshold', seconds: 200, pct: 17 },
        { zone: 5, name: 'VO2max', seconds: 100, pct: 8 },
      ],
    })
    render(<RideChart stream={stream} />)
    expect(screen.getByText('Time in zone')).toBeInTheDocument()
    expect(screen.getByText('Recovery')).toBeInTheDocument()
    expect(screen.getByText('Endurance')).toBeInTheDocument()
    expect(screen.getByText('Tempo')).toBeInTheDocument()
    expect(screen.getByText('Threshold')).toBeInTheDocument()
    expect(screen.getByText('VO2 Max')).toBeInTheDocument()
  })

  it('formats readout time as Mm SSs', () => {
    const stream = makeStream()
    render(<RideChart stream={stream} />)
    expect(screen.getByText('0m 0s')).toBeInTheDocument()
  })
})
