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

describe('AdminResumeListPage backup', () => {
  const oneResume = [
    { id: 1, name: 'Mine', is_default: true, created_at: '2024-01-01', updated_at: '2024-01-02' },
  ]
  const backupFile = () =>
    new File(
      [JSON.stringify({ format: 'someshwaran.dev/resume-backup', version: 1, resumes: [] })],
      'backup.json',
      { type: 'application/json' },
    )

  /** The list GET first, then whatever the test needs; each call a fresh Response. */
  function mockFetch(...then: Array<() => Response>) {
    let call = 0
    fetchMock.mockImplementation(() => {
      const next = call === 0 ? () => jsonResponse(oneResume) : (then[call - 1] ?? then.at(-1)!)
      call += 1
      return Promise.resolve(next())
    })
  }

  it('downloads a backup file using the admin key', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:backup')
    URL.revokeObjectURL = vi.fn()
    mockFetch(
      () =>
        new Response('{"resumes":[]}', {
          status: 200,
          headers: {
            'Content-Disposition': 'attachment; filename="someshwaran-backup-2026-11-12.json"',
          },
        }),
    )
    const user = userEvent.setup()

    renderApp('/admin')
    await user.click(await screen.findByRole('button', { name: /download backup/i }))

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/export'),
        expect.objectContaining({ headers: { Authorization: 'Bearer test-key' } }),
      ),
    )
    await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalled())
  })

  it('restores from a file and reports what was created and skipped', async () => {
    mockFetch(
      () => jsonResponse({ created: [5, 6], skipped: ['Mine'], default_id: 1 }),
      () => jsonResponse(oneResume),
    )
    const user = userEvent.setup()

    renderApp('/admin')
    await screen.findByRole('button', { name: /restore from file/i })
    await user.upload(screen.getByLabelText('Backup file'), backupFile())

    expect(
      await screen.findByText(/restored 2 resumes; skipped 1 that already exist \(Mine\)/i),
    ).toBeInTheDocument()
    const post = fetchMock.mock.calls.find(([, o]) => o?.method === 'POST')!
    expect(post[0]).toContain('/api/admin/import?replace=false')
  })

  it('asks before replacing everything, and does nothing if you decline', async () => {
    mockFetch(() => jsonResponse({ created: [], skipped: [], default_id: null }))
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const user = userEvent.setup()

    renderApp('/admin')
    await screen.findByRole('button', { name: /restore from file/i })
    await user.click(screen.getByLabelText(/replace all existing resumes/i))
    await user.upload(screen.getByLabelText('Backup file'), backupFile())

    expect(window.confirm).toHaveBeenCalledWith(
      expect.stringMatching(/deletes all 1 existing resume/i),
    )
    expect(fetchMock.mock.calls.some(([, o]) => o?.method === 'POST')).toBe(false)
  })

  it('sends replace=true once confirmed', async () => {
    mockFetch(
      () => jsonResponse({ created: [9], skipped: [], default_id: 9 }),
      () => jsonResponse(oneResume),
    )
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const user = userEvent.setup()

    renderApp('/admin')
    await screen.findByRole('button', { name: /restore from file/i })
    await user.click(screen.getByLabelText(/replace all existing resumes/i))
    await user.upload(screen.getByLabelText('Backup file'), backupFile())

    await screen.findByText(/restored 1 resume\./i)
    const post = fetchMock.mock.calls.find(([, o]) => o?.method === 'POST')!
    expect(post[0]).toContain('replace=true')
  })

  it('rejects a file that is not JSON without calling the server', async () => {
    mockFetch(() => jsonResponse({}))
    const user = userEvent.setup()

    renderApp('/admin')
    await screen.findByRole('button', { name: /restore from file/i })
    await user.upload(
      screen.getByLabelText('Backup file'),
      new File(['this is not json'], 'bad.json', { type: 'application/json' }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(/isn.t valid JSON/i)
    expect(fetchMock.mock.calls.some(([, o]) => o?.method === 'POST')).toBe(false)
  })

  it("shows the server's reason and says nothing was changed when the file is rejected", async () => {
    mockFetch(() =>
      jsonResponse(
        {
          detail: [
            {
              loc: ['body', 'resumes', 0, 'summary'],
              msg: 'String should have at most 4000 characters',
            },
          ],
        },
        422,
      ),
    )
    const user = userEvent.setup()

    renderApp('/admin')
    await screen.findByRole('button', { name: /restore from file/i })
    await user.upload(screen.getByLabelText('Backup file'), backupFile())

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/nothing was changed/i)
    expect(alert).toHaveTextContent(
      /resumes\.0\.summary: String should have at most 4000 characters/,
    )
  })
})
