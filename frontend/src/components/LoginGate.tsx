import { type ReactNode, useEffect, useState } from 'react'

import { getSession, login, logout } from '../lib/api'
import { Button } from './ui/Button'
import { Card } from './ui/Card'

export function LoginGate({ children }: { children: ReactNode }) {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    void getSession()
      .then(({ authenticated: next }) => setAuthenticated(next))
      .catch(() => {
        setError('Could not check the current session.')
        setAuthenticated(false)
      })
  }, [])

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login(password)
      setPassword('')
      setAuthenticated(true)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not sign in.')
    } finally {
      setSubmitting(false)
    }
  }

  async function signOut() {
    await logout()
    setAuthenticated(false)
  }

  if (authenticated === null) {
    return <main className="grid min-h-screen place-items-center bg-zinc-50 text-sm text-zinc-500">Checking session…</main>
  }

  if (!authenticated) {
    return <main className="grid min-h-screen place-items-center bg-zinc-50 px-6"><Card className="w-full max-w-md"><form className="p-8" onSubmit={(event) => void submit(event)}><p className="text-sm font-medium text-zinc-500">Northstar Facilities B.V.</p><h1 className="mt-2 text-2xl font-semibold tracking-tight">Document review</h1><p className="mt-2 text-sm leading-6 text-zinc-600">Enter the shared review password to continue.</p><label className="mt-6 block text-sm font-medium text-zinc-800">Password<input className="mt-2 h-10 w-full rounded-lg border border-zinc-200 bg-white px-3 text-sm" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required autoFocus /></label>{error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}<Button className="mt-6 w-full" disabled={submitting}>{submitting ? 'Signing in…' : 'Sign in'}</Button></form></Card></main>
  }

  return <>{children}<button type="button" onClick={() => void signOut()} className="fixed bottom-4 right-4 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-medium text-zinc-600 shadow-sm hover:bg-zinc-50">Sign out</button></>
}
