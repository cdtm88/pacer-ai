import { useState } from 'react'
import { useNavigate } from 'react-router'
import { Check } from 'lucide-react'
import { supabase } from '../lib/supabase'
import { useAuthStore } from '../stores/authStore'
import { ZONE_SPECTRUM } from '@/lib/zones'

type Mode = 'signin' | 'signup'

const BENEFITS = ['Structured plan in minutes', 'Adapts to every ride', 'No FTP required']

function BrandMark() {
  return (
    <div className="mb-6 px-1">
      <div
        className="text-4xl font-bold leading-none"
        style={{ color: 'var(--color-ink)', letterSpacing: '-0.03em' }}
      >
        Pace
      </div>
      <div
        className="mt-2.5 h-[3px] w-[72px] rounded-full"
        style={{ background: ZONE_SPECTRUM }}
      />
    </div>
  )
}

export function LoginScreen() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [awaitingConfirmation, setAwaitingConfirmation] = useState(false)

  function clearError() {
    if (error) setError('')
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (!email.trim()) { setError('Enter your email address'); return }
    if (!password) { setError('Enter your password'); return }
    if (mode === 'signup' && password.length < 6) {
      setError('Password must be at least 6 characters')
      return
    }

    setLoading(true)

    if (mode === 'signin') {
      const { data, error: err } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      })
      setLoading(false)

      if (err) {
        setError(
          err.message === 'Invalid login credentials'
            ? 'Incorrect email or password.'
            : err.message,
        )
        return
      }

      useAuthStore.getState().setAuth({
        session: data.session,
        user: data.user,
        isLoading: false,
      })
      navigate('/', { replace: true })
    } else {
      const { data, error: err } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback`,
        },
      })
      setLoading(false)

      if (err) {
        setError(err.message)
        return
      }

      if (data.session) {
        // Email confirmation disabled — session is immediate
        useAuthStore.getState().setAuth({
          session: data.session,
          user: data.user!,
          isLoading: false,
        })
        navigate('/', { replace: true })
      } else {
        // Email confirmation required — wait for user to click link
        setAwaitingConfirmation(true)
      }
    }
  }

  if (awaitingConfirmation) {
    return (
      <div
        className="min-h-screen flex items-center justify-center px-4"
        style={{ backgroundColor: 'var(--color-bg)' }}
      >
        <div
          className="w-full max-w-[400px] rounded-2xl p-8 shadow-sm border"
          style={{ borderColor: 'var(--color-line)', backgroundColor: 'var(--color-surface)' }}
        >
          <h1 className="text-2xl font-semibold mb-3" style={{ color: 'var(--color-ink)' }}>
            Check your email
          </h1>
          <p className="text-base" style={{ color: 'var(--color-ink-2)' }}>
            We sent a confirmation link to {email}. Click it to activate your account, then sign in.
          </p>
          <button
            className="mt-6 text-sm font-medium"
            style={{ color: 'var(--color-blue-6)' }}
            onClick={() => { setAwaitingConfirmation(false); setMode('signin') }}
          >
            Back to sign in
          </button>
        </div>
      </div>
    )
  }

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center px-4 py-10"
      style={{ backgroundColor: 'var(--color-bg)' }}
    >
      <div className="w-full max-w-[400px]">
        <BrandMark />

        <div
          className="w-full rounded-2xl p-8 shadow-sm border"
          style={{ borderColor: 'var(--color-line)', backgroundColor: 'var(--color-surface)' }}
        >
          <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--color-ink)' }}>
            PacerAI
          </h1>
          <p className="text-sm mb-4" style={{ color: 'var(--color-ink-2)' }}>
            Your adaptive cycling coach.
          </p>

          {/* Benefit bullets: fill the vertical space and sell the product */}
          <ul className="mb-6 space-y-1.5">
            {BENEFITS.map((b) => (
              <li key={b} className="flex items-center gap-2 text-sm" style={{ color: 'var(--color-ink-2)' }}>
                <Check size={15} strokeWidth={2.5} style={{ color: 'var(--color-brand)', flexShrink: 0 }} />
                {b}
              </li>
            ))}
          </ul>

          {/* Mode tabs */}
        <div className="flex mb-6 border-b" style={{ borderColor: 'var(--color-line)' }}>
          {(['signin', 'signup'] as Mode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { setMode(m); setError('') }}
              className="pb-2 mr-5 text-sm font-medium border-b-2 -mb-px transition-colors"
              style={{
                borderColor: mode === m ? 'var(--color-blue-6)' : 'transparent',
                color: mode === m ? 'var(--color-blue-6)' : 'var(--color-ink-2)',
              }}
            >
              {m === 'signin' ? 'Sign in' : 'Create account'}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className="mb-4">
            <label
              htmlFor="email"
              className="block text-sm font-medium mb-1.5"
              style={{ color: 'var(--color-ink)' }}
            >
              Email address
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => { setEmail(e.target.value); clearError() }}
              placeholder="you@example.com"
              autoComplete="email"
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none transition-colors"
              style={{
                borderColor: 'var(--color-line)',
                color: 'var(--color-ink)',
                backgroundColor: 'var(--color-surface)',
              }}
            />
          </div>

          <div className="mb-6">
            <label
              htmlFor="password"
              className="block text-sm font-medium mb-1.5"
              style={{ color: 'var(--color-ink)' }}
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); clearError() }}
              placeholder={mode === 'signup' ? 'At least 6 characters' : ''}
              autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none transition-colors"
              style={{
                borderColor: 'var(--color-line)',
                color: 'var(--color-ink)',
                backgroundColor: 'var(--color-surface)',
              }}
            />
          </div>

          {error && (
            <p
              className="mb-4 text-sm"
              style={{ color: 'var(--color-bad)' }}
              role="alert"
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 active:opacity-80 disabled:opacity-50"
            style={{ backgroundColor: 'var(--color-blue-6)' }}
          >
            {loading ? 'Please wait...' : mode === 'signin' ? 'Sign in' : 'Create account'}
          </button>
        </form>
        </div>
      </div>
    </div>
  )
}
