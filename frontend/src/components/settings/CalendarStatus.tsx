import { useState } from 'react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { useCalendarStatus } from '@/hooks/useCalendarStatus'
import { disconnectCalendar } from '@/lib/api'
import { supabase } from '@/lib/supabase'

const API_URL = import.meta.env.VITE_API_URL as string

export function CalendarStatus() {
  const { data, isLoading } = useCalendarStatus()
  const queryClient = useQueryClient()
  const [disconnecting, setDisconnecting] = useState(false)

  async function handleConnect() {
    const { data: sessionData } = await supabase.auth.getSession()
    const token = sessionData.session?.access_token ?? ''
    window.location.href = `${API_URL}/calendar/auth?token=${encodeURIComponent(token)}`
  }

  async function handleDisconnect() {
    setDisconnecting(true)
    try {
      await disconnectCalendar()
      await queryClient.invalidateQueries({ queryKey: ['calendar', 'settings'] })
      toast.success('Google Calendar disconnected.')
    } catch {
      toast.error('Could not disconnect. Please try again.')
    } finally {
      setDisconnecting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--color-ink-2)' }}>
        <span
          className="inline-block w-4 h-4 rounded-full border-2 border-current border-t-transparent animate-spin"
          aria-label="Checking calendar status"
        />
        Checking...
      </div>
    )
  }

  if (data?.connected) {
    return (
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
            style={{ backgroundColor: 'var(--color-success-bg, #dcfce7)', color: 'var(--color-success, #16a34a)' }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-current" />
            Connected
          </span>
          <span className="text-sm" style={{ color: 'var(--color-ink-2)' }}>
            Google Calendar
          </span>
        </div>

        <AlertDialog>
          <AlertDialogTrigger asChild>
            <button
              className="text-sm underline"
              style={{ color: 'var(--color-ink-2)' }}
              disabled={disconnecting}
            >
              Disconnect
            </button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Disconnect Google Calendar?</AlertDialogTitle>
              <AlertDialogDescription>
                PacerAI will stop syncing sessions to your Google Calendar. Existing events
                will remain in your calendar. You can reconnect at any time.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDisconnect}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                Disconnect
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    )
  }

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={handleConnect}
    >
      Connect Google Calendar
    </Button>
  )
}
