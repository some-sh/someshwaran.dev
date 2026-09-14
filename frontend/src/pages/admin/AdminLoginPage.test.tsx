import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearAdminKey, getAdminKey } from '@/lib/api'
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

describe('AdminLoginPage', () => {
  it('saves the key and navigates to /admin once it verifies', async () => {
    // First call is whoami (the verify step); once on /admin, the real
    // AdminResumeListPage fetches the list too — give it an empty one.
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ authenticated: true }))
      .mockResolvedValue(jsonResponse([]))
    const user = userEvent.setup()

    renderApp('/admin/login')

    await user.type(await screen.findByLabelText(/api key/i), 'correct-key')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByRole('heading', { name: 'Resumes' })).toBeInTheDocument()
    expect(getAdminKey()).toBe('correct-key')
  })

  it('shows an error and does not save the key when it is rejected', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'Invalid or missing API key' }, 401))
    const user = userEvent.setup()

    renderApp('/admin/login')

    await user.type(await screen.findByLabelText(/api key/i), 'wrong-key')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText(/invalid api key/i)).toBeInTheDocument()
    expect(getAdminKey()).toBeNull()
  })
})
