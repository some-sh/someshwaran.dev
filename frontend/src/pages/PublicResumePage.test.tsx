import { screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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
    id: 1,
    name: 'Internal label',
    is_default: true,
    headline: '',
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
    ...overrides,
  }
}

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
})

describe('PublicResumePage', () => {
  it('shows a not-found message when there is no default resume', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'No default resume is set' }, 404))

    renderApp('/')

    expect(await screen.findByText(/no resume has been published yet/i)).toBeInTheDocument()
  })

  it('renders resume content once loaded', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        id: 1,
        name: 'Backend-focused',
        is_default: true,
        headline: 'Senior SDET | Python',
        summary: 'Backend engineer.',
        created_at: '2024-01-01T00:00:00',
        updated_at: '2024-01-01T00:00:00',
        personal_info: {
          id: 1,
          full_name: 'Ada Lovelace',
          email: 'ada@example.com',
          phone: null,
          location: 'Chennai, India',
          website: null,
          github: null,
          linkedin: null,
        },
        skills: [{ id: 1, name: 'Python', category: 'Languages' }],
        experience: [
          {
            id: 1,
            company: 'Acme',
            role: 'SDET',
            location: null,
            start_date: '2022-01-01',
            end_date: null,
            highlights: [{ text: 'Built the test framework', group: null }],
          },
        ],
        projects: [],
        education: [],
        certifications: [],
      }),
    )

    renderApp('/')

    expect(await screen.findByRole('heading', { name: 'Ada Lovelace' })).toBeInTheDocument()
    expect(screen.getByText('Backend engineer.')).toBeInTheDocument()
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('SDET, Acme')).toBeInTheDocument()
    expect(screen.getByText('Built the test framework')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /download pdf/i })).toBeInTheDocument()
  })

  it('shows experience as month-year and education as years only', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        id: 1,
        name: 'Senior SDET',
        is_default: true,
        headline: '',
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
        experience: [
          {
            id: 1,
            company: 'Acme',
            role: 'SDET',
            location: null,
            start_date: '2019-05-01',
            end_date: null,
            highlights: [],
          },
        ],
        projects: [],
        education: [
          {
            id: 1,
            institution: 'MNM Jain',
            degree: 'B.E.',
            field_of_study: 'ECE',
            start_date: '2015-01-01',
            end_date: '2019-01-01',
          },
        ],
        certifications: [],
      }),
    )

    renderApp('/')

    expect(await screen.findByText(/May 2019/)).toBeInTheDocument()
    expect(screen.getByText(/Present/)).toBeInTheDocument()
    // Years only: the stored January is a placeholder, not a fact to display.
    expect(screen.getByText('2015 – 2019')).toBeInTheDocument()
    expect(screen.queryByText(/Jan 2019/)).not.toBeInTheDocument()
  })

  it('shows a generic error message for a non-404 failure', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'boom' }, 500))

    renderApp('/')

    await waitFor(() => expect(screen.getByText(/couldn.t load the resume/i)).toBeInTheDocument())
  })
  it('shows the headline, links the email and safe URLs, and never links an unsafe one', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        resumeFixture({
          headline: 'Senior SDET | Python, Playwright',
          personal_info: {
            id: 1,
            full_name: 'Ada Lovelace',
            email: 'ada@example.com',
            phone: null,
            location: 'London',
            website: 'javascript:alert(1)',
            github: null,
            linkedin: 'https://www.linkedin.com/in/ada',
          },
        }),
      ),
    )

    renderApp('/')

    expect(await screen.findByText('Senior SDET | Python, Playwright')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'ada@example.com' })).toHaveAttribute(
      'href',
      'mailto:ada@example.com',
    )
    expect(screen.getByRole('link', { name: 'linkedin.com/in/ada' })).toHaveAttribute(
      'href',
      'https://www.linkedin.com/in/ada',
    )
    // Shown, but as text: no link is ever built from a javascript: value.
    expect(screen.getByText(/javascript:alert\(1\)/)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /javascript/ })).not.toBeInTheDocument()
  })

  it('renders grouped highlights under their sub-headings', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        resumeFixture({
          experience: [
            {
              id: 1,
              company: 'Acme',
              role: 'SDET',
              location: null,
              start_date: '2019-05-01',
              end_date: null,
              highlights: [
                { text: 'Built the platform', group: 'Engineering platform' },
                { text: 'Cut setup time', group: 'Engineering platform' },
                { text: 'Validated releases', group: 'Release quality' },
              ],
            },
          ],
        }),
      ),
    )

    renderApp('/')

    expect(await screen.findByText('Engineering platform')).toBeInTheDocument()
    expect(screen.getByText('Release quality')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'Built the platform',
      'Cut setup time',
      'Validated releases',
    ])
  })

  it('sets the tab title to the name and headline, and restores it on leaving', async () => {
    fetchMock.mockResolvedValue(jsonResponse(resumeFixture({ headline: 'Senior SDET' })))

    const { unmount } = renderApp('/')

    await waitFor(() => expect(document.title).toBe('Ada Lovelace — Senior SDET'))
    unmount()
    expect(document.title).toBe('someshwaran.dev')
  })
})
