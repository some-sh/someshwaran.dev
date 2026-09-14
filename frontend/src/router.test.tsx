/**
 * Routing-level tests: the beforeLoad guards on /admin and /admin/login
 * (router.tsx) and the not-found fallback — exercised through the real
 * route tree rather than a stand-in guard component.
 */
import { screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearAdminKey, setAdminKey } from '@/lib/api'
import { renderApp } from '@/test/renderApp'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const fetchMock = vi.fn()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
  clearAdminKey()
})

describe('routing', () => {
  it('redirects an admin route to /admin/login when no key is set', async () => {
    renderApp('/admin')

    // CardTitle renders a styled <div>, not a semantic heading element.
    expect(await screen.findByText(/admin sign-in/i)).toBeInTheDocument()
  })

  it('redirects away from /admin/login when a key is already set', async () => {
    setAdminKey('test-key')
    fetchMock.mockResolvedValue(jsonResponse([]))

    renderApp('/admin/login')

    expect(await screen.findByRole('heading', { name: 'Resumes' })).toBeInTheDocument()
  })

  it('shows a not-found page for an unmatched route', async () => {
    renderApp('/this-route-does-not-exist')

    expect(await screen.findByText(/page not found/i)).toBeInTheDocument()
  })
})
