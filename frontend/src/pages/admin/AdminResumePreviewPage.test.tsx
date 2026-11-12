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

function resumeFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    name: 'Draft for backend roles',
    is_default: false,
    headline: 'Backend engineer',
    summary: 'Builds services.',
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
    ...overrides,
  }
}

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  setAdminKey('test-key')
})

afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
  clearAdminKey()
})

describe('AdminResumePreviewPage', () => {
  it('renders a non-default resume through the admin endpoint, marked as not published', async () => {
    fetchMock.mockResolvedValue(jsonResponse(resumeFixture()))

    renderApp('/admin/resumes/7/preview')

    expect(await screen.findByRole('heading', { name: 'Ada Lovelace' })).toBeInTheDocument()
    expect(screen.getByText('Backend engineer')).toBeInTheDocument()
    expect(screen.getByText('Not published')).toBeInTheDocument()
    // The public endpoint only serves the default resume; a draft must come from /api/admin.
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/admin/resumes/7')
    // No download buttons here: those belong to the public page.
    expect(screen.queryByRole('link', { name: /download pdf/i })).not.toBeInTheDocument()
  })

  it('marks the default resume as published', async () => {
    fetchMock.mockResolvedValue(jsonResponse(resumeFixture({ is_default: true })))

    renderApp('/admin/resumes/7/preview')

    expect(await screen.findByText('Published (default)')).toBeInTheDocument()
  })

  it('shows an error when the resume does not exist', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'Resume not found' }, 404))

    renderApp('/admin/resumes/99/preview')

    expect(await screen.findByText(/couldn’t load this resume/i)).toBeInTheDocument()
  })

  it('requires the admin key', async () => {
    clearAdminKey()

    renderApp('/admin/resumes/7/preview')

    expect(await screen.findByLabelText(/api key/i)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
