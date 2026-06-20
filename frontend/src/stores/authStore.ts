import { create } from 'zustand'
import type { Session, User } from '@supabase/supabase-js'

interface AuthState {
  session: Session | null
  user: User | null
  isLoading: boolean
  setAuth: (auth: { session: Session | null; user: User | null; isLoading: boolean }) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  session: null,
  user: null,
  isLoading: true,
  setAuth: ({ session, user, isLoading }) => set({ session, user, isLoading }),
}))
