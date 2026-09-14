import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
  setAdminKey('test-key')
})

afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
  clearAdminKey()
})

describe('AdminResumeListPage', () => {
  it('renders the resume list once loaded', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse([
        {
          id: 1,
          name: 'Backend-focused',
          is_default: true,
          created_at: '2024-01-01',
          updated_at: '2024-01-02',
        },
        {
          id: 2,
          name: 'Frontend-focused',
          is_default: false,
          created_at: '2024-01-01',
          updated_at: '2024-01-02',
        },
      ]),
    )

    renderApp('/admin')

    expect(await screen.findByRole('link', { name: 'Backend-focused' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Frontend-focused' })).toBeInTheDocument()
    expect(screen.getByText('Default')).toBeInTheDocument()
  })

  it('shows an empty-state message when there are no resumes', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]))

    renderApp('/admin')

    expect(await screen.findByText(/no resumes yet/i)).toBeInTheDocument()
  })

  it('calls set-default and refreshes the list when clicked', async () => {
    const listResponse = jsonResponse([
      {
        id: 1,
        name: 'Only resume',
        is_default: false,
        created_at: '2024-01-01',
        updated_at: '2024-01-02',
      },
    ])
    fetchMock
      .mockResolvedValueOnce(listResponse)
      .mockResolvedValueOnce(jsonResponse({ id: 1 }))
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: 1,
            name: 'Only resume',
            is_default: true,
            created_at: '2024-01-01',
            updated_at: '2024-01-02',
          },
        ]),
      )
    const user = userEvent.setup()

    renderApp('/admin')

    await screen.findByRole('link', { name: 'Only resume' })
    await user.click(screen.getByRole('button', { name: /set default/i }))

    await waitFor(() => expect(screen.getByText('Default')).toBeInTheDocument())
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('/api/admin/resumes/1/set-default'),
      expect.objectContaining({ method: 'POST' }),
    )
  })
})
