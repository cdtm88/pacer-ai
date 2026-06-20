import { useQuery } from '@tanstack/react-query'
import { getCalendarSettings, type CalendarSettings } from '@/lib/api'

export function useCalendarStatus() {
  return useQuery<CalendarSettings>({
    queryKey: ['calendar', 'settings'],
    queryFn: getCalendarSettings,
    staleTime: 30_000,
  })
}
