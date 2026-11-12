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
  /** Seconds to wait before retrying, from a 429's Retry-After header. */
  retryAfterSeconds: number | null

  constructor(status: number, message: string, retryAfterSeconds: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.retryAfterSeconds = retryAfterSeconds
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

/**
 * Turns an API error body's ``detail`` into text a person can act on. FastAPI
 * sends a string for most errors but a list of ``{loc, msg}`` items for
 * validation failures (422); showing only the status text ("Unprocessable
 * Entity") would hide which field was wrong.
 */
export function describeDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item?.msg !== 'string') return null
        const path = Array.isArray(item.loc)
          ? item.loc.filter((part: unknown) => part !== 'body').join('.')
          : ''
        return path ? `${path}: ${item.msg}` : item.msg
      })
      .filter((part): part is string => part !== null)
    if (parts.length > 0) return parts.slice(0, 3).join('; ')
  }
  return fallback
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
    const retryAfter = Number(response.headers.get('Retry-After'))
    throw new ApiError(
      response.status,
      describeDetail(body?.detail, response.statusText),
      Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null,
    )
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

export type KeyCheck =
  | { result: 'ok' }
  | { result: 'invalid' }
  | { result: 'locked'; retryAfterSeconds: number | null }
  | { result: 'error' }

/** Used by the login screen to validate a key the user just typed, before
 * committing it to localStorage via setAdminKey. "locked" means the server
 * has throttled this address after repeated wrong keys (HTTP 429) — a
 * different situation from a wrong key, and the right key is refused too. */
export async function checkAdminKey(key: string): Promise<KeyCheck> {
  try {
    await request('/api/admin/whoami', {}, key)
    return { result: 'ok' }
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 429)
        return { result: 'locked', retryAfterSeconds: error.retryAfterSeconds }
      if (error.status === 401 || error.status === 403) return { result: 'invalid' }
    }
    return { result: 'error' }
  }
}

export async function verifyAdminKey(key: string): Promise<boolean> {
  return (await checkAdminKey(key)).result === 'ok'
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

  saveBlob(await response.blob(), `${filenameHint}.${format}`)
}

function saveBlob(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}

// --- Admin: backup and restore ---

export interface ImportResult {
  created: number[]
  skipped: string[]
  default_id: number | null
}

/** Downloads every resume as one JSON backup file. */
export async function downloadBackup(): Promise<void> {
  const key = getAdminKey()
  if (!key) {
    throw new ApiError(401, 'No admin API key is set')
  }
  const response = await fetch(`${API_BASE_URL}/api/admin/export`, {
    headers: { Authorization: `Bearer ${key}` },
  })
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText)
  }
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? 'someshwaran-backup.json'
  saveBlob(await response.blob(), filename)
}

/** Restores a parsed backup file. All or nothing on the server; with
 * ``replace`` every existing resume is deleted first. */
export const restoreBackup = (backup: unknown, replace: boolean): Promise<ImportResult> =>
  adminFetch(`/api/admin/import?replace=${replace}`, {
    method: 'POST',
    body: JSON.stringify(backup),
  })
