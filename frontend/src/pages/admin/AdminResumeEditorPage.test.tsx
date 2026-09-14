import { screen } from '@testing-library/react'
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

describe('AdminResumeEditorPage', () => {
  it('starts blank in create mode and posts a create request on submit', async () => {
    // The real backend returns the full saved resume; the create
    // mutation seeds the query cache with exactly this response before
    // navigating to /admin/resumes/9, so it needs to be a complete,
    // valid Resume — not just {id: 9} — or the edit-mode render that
    // follows would crash trying to read its (missing) fields.
    fetchMock.mockResolvedValue(
      jsonResponse(
        {
          id: 9,
          name: 'My resume',
          is_default: false,
          summary: '',
          created_at: '2024-01-01T00:00:00',
          updated_at: '2024-01-01T00:00:00',
          personal_info: {
            id: 1,
            full_name: 'Ada Lovelace',
            email: 'ada@example.com',
            phone: null,
            location: null,
            website: null,
            github: null,
            linkedin: null,
          },
          skills: [],
          experience: [],
          projects: [],
          education: [],
          certifications: [],
        },
        201,
      ),
    )
    const user = userEvent.setup()

    renderApp('/admin/resumes/new')

    expect(await screen.findByRole('heading', { name: /new resume/i })).toBeInTheDocument()

    await user.type(screen.getByLabelText(/internal name/i), 'My resume')
    await user.type(screen.getByLabelText(/full name/i), 'Ada Lovelace')
    await user.type(screen.getByLabelText(/^email$/i), 'ada@example.com')
    await user.click(screen.getByRole('button', { name: /^save$/i }))

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/resumes'),
      expect.objectContaining({ method: 'POST' }),
    )
    const [, options] = fetchMock.mock.calls[0]
    const body = JSON.parse(options.body)
    expect(body.name).toBe('My resume')
    expect(body.personal_info.full_name).toBe('Ada Lovelace')
    expect(body.skills).toEqual([])

    expect(await screen.findByRole('heading', { name: /edit resume/i })).toBeInTheDocument()
  })

  it('loads existing resume content in edit mode', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        id: 3,
        name: 'Existing resume',
        is_default: false,
        summary: 'A summary.',
        created_at: '2024-01-01T00:00:00',
        updated_at: '2024-01-01T00:00:00',
        personal_info: {
          id: 1,
          full_name: 'Grace Hopper',
          email: 'grace@example.com',
          phone: null,
          location: null,
          website: null,
          github: null,
          linkedin: null,
        },
        skills: [{ id: 1, name: 'COBOL', category: null }],
        experience: [],
        projects: [],
        education: [],
        certifications: [],
      }),
    )

    renderApp('/admin/resumes/3')

    expect(await screen.findByDisplayValue('Existing resume')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Grace Hopper')).toBeInTheDocument()
    expect(screen.getByDisplayValue('COBOL')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /edit resume/i })).toBeInTheDocument()
  })

  it('adds a skill row when "Add skill" is clicked', async () => {
    const user = userEvent.setup()

    renderApp('/admin/resumes/new')
    await screen.findByRole('heading', { name: /new resume/i })

    const before = screen.queryAllByLabelText(/^name$/i).length
    await user.click(screen.getByRole('button', { name: /add skill/i }))

    expect(screen.queryAllByLabelText(/^name$/i)).toHaveLength(before + 1)
  })
})
