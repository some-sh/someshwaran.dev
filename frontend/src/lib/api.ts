/**
 * Thin fetch wrapper for the resume API (backend/app/api/public.py,
 * backend/app/api/admin.py). Two entry points, mirroring the backend's
 * two routers: `apiFetch` for public routes, `adminFetch` for admin
 * routes, which attaches the API key from localStorage as a bearer
 * token — the same single auth mechanism the backend expects (see
 * CLAUDE.md's Auth section).
 */
import type { Resume, ResumeInput, ResumeSummary } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''
const ADMIN_KEY_STORAGE_KEY = 'someshwaran-dev.admin-api-key'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function getAdminKey(): string | null {
  try {
    return localStorage.getItem(ADMIN_KEY_STORAGE_KEY)
  } catch {
    return null
  }
}

export function setAdminKey(key: string): void {
  localStorage.setItem(ADMIN_KEY_STORAGE_KEY, key)
}

export function clearAdminKey(): void {
  localStorage.removeItem(ADMIN_KEY_STORAGE_KEY)
}

async function request<T>(path: string, options: RequestInit = {}, key?: string): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (options.body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }
  if (key) {
    headers.set('Authorization', `Bearer ${key}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const message = body?.detail ?? response.statusText
    throw new ApiError(response.status, typeof message === 'string' ? message : response.statusText)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  return request<T>(path, options)
}

function adminFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const key = getAdminKey()
  if (!key) {
    // A rejected promise, not a thrown error: every caller here treats
    // this as `await`-able / `.catch()`-able, and a synchronous throw
    // from a function typed to return a Promise breaks that for anyone
    // who hasn't wrapped the call in try/catch.
    return Promise.reject(new ApiError(401, 'No admin API key is set'))
  }
  return request<T>(path, options, key)
}

// --- Public routes ---

export const getDefaultResume = (): Promise<Resume> => apiFetch('/api/resumes/default')

export const defaultResumeExportUrl = (format: 'pdf' | 'docx'): string =>
  `${API_BASE_URL}/api/resumes/default/export.${format}`

// --- Admin: verifying a key before it's saved ---

/** Used by the login screen to validate a key the user just typed, before
 * committing it to localStorage via setAdminKey. */
export async function verifyAdminKey(key: string): Promise<boolean> {
  try {
    await request('/api/admin/whoami', {}, key)
    return true
  } catch {
    return false
  }
}

// --- Admin: resume CRUD ---

export const listResumes = (): Promise<ResumeSummary[]> => adminFetch('/api/admin/resumes')

export const getResumeById = (id: number): Promise<Resume> => adminFetch(`/api/admin/resumes/${id}`)

export const createResume = (input: ResumeInput): Promise<Resume> =>
  adminFetch('/api/admin/resumes', { method: 'POST', body: JSON.stringify(input) })

export const updateResume = (id: number, input: ResumeInput): Promise<Resume> =>
  adminFetch(`/api/admin/resumes/${id}`, { method: 'PATCH', body: JSON.stringify(input) })

export const deleteResume = (id: number): Promise<void> =>
  adminFetch(`/api/admin/resumes/${id}`, { method: 'DELETE' })

export const cloneResume = (id: number): Promise<Resume> =>
  adminFetch(`/api/admin/resumes/${id}/clone`, { method: 'POST' })

export const setDefaultResume = (id: number): Promise<Resume> =>
  adminFetch(`/api/admin/resumes/${id}/set-default`, { method: 'POST' })

/** Admin exports need the same Authorization header as every other admin
 * route, so — unlike the public export, a plain `<a href>` — this fetches
 * the file as a blob and triggers the save itself. (A `?key=` query param
 * was the other option; rejected because it'd land in browser history and
 * server access logs, and the backend deliberately only reads the
 * Authorization header.) */
export async function downloadAdminExport(
  id: number,
  format: 'pdf' | 'docx',
  filenameHint: string,
): Promise<void> {
  const key = getAdminKey()
  if (!key) {
    throw new ApiError(401, 'No admin API key is set')
  }

  const response = await fetch(`${API_BASE_URL}/api/admin/resumes/${id}/export.${format}`, {
    headers: { Authorization: `Bearer ${key}` },
  })
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText)
  }

  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = `${filenameHint}.${format}`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}
