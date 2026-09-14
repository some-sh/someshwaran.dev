import { useNavigate } from '@tanstack/react-router'
import { type FormEvent, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { setAdminKey, verifyAdminKey } from '@/lib/api'

/** "Already have a key" is handled by this route's own beforeLoad
 * (router.tsx) — it never reaches this component in that case. */
export function AdminLoginPage() {
  const navigate = useNavigate()
  const [key, setKey] = useState('')
  const [status, setStatus] = useState<'idle' | 'checking' | 'invalid'>('idle')

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setStatus('checking')
    const trimmed = key.trim()
    const ok = await verifyAdminKey(trimmed)
    if (!ok) {
      setStatus('invalid')
      return
    }
    setAdminKey(trimmed)
    await navigate({ to: '/admin', replace: true })
  }

  return (
    <main className="flex min-h-svh items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Admin sign-in</CardTitle>
          <CardDescription>Paste the API key configured for this deployment.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="admin-key">API key</Label>
              <Input
                id="admin-key"
                type="password"
                autoComplete="off"
                value={key}
                onChange={(event) => setKey(event.target.value)}
                required
              />
            </div>
            {status === 'invalid' && <p className="text-destructive text-sm">Invalid API key.</p>}
            <Button type="submit" disabled={status === 'checking' || key.trim() === ''}>
              {status === 'checking' ? 'Checking…' : 'Sign in'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
