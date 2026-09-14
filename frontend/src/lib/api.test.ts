import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  clearAdminKey,
  createResume,
  defaultResumeExportUrl,
  getAdminKey,
  getDefaultResume,
  setAdminKey,
  verifyAdminKey,
} from './api'
import type { ResumeInput } from './types'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('admin key storage', () => {
  afterEach(() => {
    clearAdminKey()
  })

  it('round-trips through localStorage', () => {
    expect(getAdminKey()).toBeNull()
    setAdminKey('secret-key')
    expect(getAdminKey()).toBe('secret-key')
    clearAdminKey()
    expect(getAdminKey()).toBeNull()
  })
})

describe('defaultResumeExportUrl', () => {
  it('builds the public export path for a format', () => {
    expect(defaultResumeExportUrl('pdf')).toMatch(/\/api\/resumes\/default\/export\.pdf$/)
    expect(defaultResumeExportUrl('docx')).toMatch(/\/api\/resumes\/default\/export\.docx$/)
  })
})

describe('getDefaultResume', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it('returns the parsed resume on success', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 1, name: 'Default' }))

    const resume = await getDefaultResume()

    expect(resume).toEqual({ id: 1, name: 'Default' })
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/resumes/default'),
      expect.objectContaining({ headers: expect.any(Headers) }),
    )
  })

  it('throws an ApiError carrying the response status and detail', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'No default resume is set' }, 404))

    await expect(getDefaultResume()).rejects.toMatchObject({
      status: 404,
      message: 'No default resume is set',
    })
  })
})

describe('verifyAdminKey', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it('returns true for a valid key and sends it as a bearer token', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ authenticated: true }))

    const ok = await verifyAdminKey('good-key')

    expect(ok).toBe(true)
    const [, options] = fetchMock.mock.calls[0]
    expect((options.headers as Headers).get('Authorization')).toBe('Bearer good-key')
  })

  it('returns false for a rejected key instead of throwing', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'Invalid or missing API key' }, 401))

    await expect(verifyAdminKey('bad-key')).resolves.toBe(false)
  })
})

describe('createResume', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
    clearAdminKey()
  })

  it('throws without making a request when no admin key is set', async () => {
    const input: ResumeInput = {
      name: 'x',
      summary: '',
      personal_info: {
        full_name: 'x',
        email: 'x@example.com',
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
    }

    await expect(createResume(input)).rejects.toMatchObject({ status: 401 })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('sends the admin key and JSON body when one is set', async () => {
    setAdminKey('the-key')
    fetchMock.mockResolvedValue(jsonResponse({ id: 5 }, 201))

    const input: ResumeInput = {
      name: 'x',
      summary: '',
      personal_info: {
        full_name: 'x',
        email: 'x@example.com',
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
    }

    const resume = await createResume(input)

    expect(resume).toEqual({ id: 5 })
    const [, options] = fetchMock.mock.calls[0]
    expect(options.method).toBe('POST')
    expect((options.headers as Headers).get('Authorization')).toBe('Bearer the-key')
    expect((options.headers as Headers).get('Content-Type')).toBe('application/json')
    expect(JSON.parse(options.body)).toMatchObject({ name: 'x' })
  })
})
