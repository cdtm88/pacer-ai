import { useState } from 'react'
import { toast } from 'sonner'
import { supabase } from '../lib/supabase'

function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

export function LoginScreen() {
  const [email, setEmail] = useState('')
  const [emailError, setEmailError] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [sentEmail, setSentEmail] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    // Inline validation
    if (!email.trim()) {
      setEmailError('Enter your email address')
      return
    }
    if (!isValidEmail(email.trim())) {
      setEmailError('Enter a valid email address')
      return
    }

    setEmailError('')

    const { error } = await supabase.auth.signInWithOtp({ email: email.trim() })

    if (error) {
      toast.error('Could not send magic link. Try again.')
      return
    }

    setSentEmail(email.trim())
    setSubmitted(true)
  }

  if (submitted) {
    return (
      <div
        className="min-h-screen flex items-center justify-center px-4"
        style={{ backgroundColor: 'var(--color-bg)' }}
      >
        <div
          className="w-full max-w-[400px] rounded-2xl p-8 shadow-sm border"
          style={{ borderColor: 'var(--color-line)', backgroundColor: 'var(--color-surface)' }}
        >
          <h1
            className="text-2xl font-semibold mb-3"
            style={{ color: 'var(--color-ink)' }}
          >
            Check your email
          </h1>
          <p
            className="text-base"
            style={{ color: 'var(--color-ink-2)' }}
          >
            We sent a link to {sentEmail}. Click it to sign in.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ backgroundColor: 'var(--color-bg)' }}
    >
      <div
        className="w-full max-w-[400px] rounded-2xl p-8 shadow-sm border"
        style={{ borderColor: 'var(--color-line)', backgroundColor: 'var(--color-surface)' }}
      >
        {/* Logotype */}
        <h1
          className="text-2xl font-bold mb-1"
          style={{ color: 'var(--color-ink)' }}
        >
          PacerAI
        </h1>

        {/* Descriptor */}
        <p
          className="text-sm mb-8"
          style={{ color: 'var(--color-ink-2)' }}
        >
          Your adaptive cycling coach.
        </p>

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
              onChange={(e) => {
                setEmail(e.target.value)
                if (emailError) setEmailError('')
              }}
              placeholder="you@example.com"
              autoComplete="email"
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none transition-colors"
              style={{
                borderColor: emailError ? 'var(--color-bad)' : 'var(--color-line)',
                color: 'var(--color-ink)',
                backgroundColor: 'var(--color-surface)',
              }}
              aria-describedby={emailError ? 'email-error' : undefined}
              aria-invalid={!!emailError}
            />
            {emailError && (
              <p
                id="email-error"
                className="mt-1.5 text-xs"
                style={{ color: 'var(--color-bad)' }}
                role="alert"
              >
                {emailError}
              </p>
            )}
          </div>

          <button
            type="submit"
            className="w-full rounded-lg py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 active:opacity-80"
            style={{ backgroundColor: 'var(--color-blue-6)' }}
          >
            Send magic link
          </button>
        </form>
      </div>
    </div>
  )
}
