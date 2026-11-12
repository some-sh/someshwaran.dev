/**
 * Link handling for the public page. Mirrors backend/app/services/
 * resume_document.py (safe_url / display_url), which the PDF and DOCX use:
 * the same stored value must be linked, or not, the same way on every
 * surface. Only http, https and mailto are ever linked; anything else (for
 * example "javascript:...") is shown as plain text.
 */
const LINKABLE = new Set(['http:', 'https:', 'mailto:'])
const HAS_SCHEME = /^[a-zA-Z][a-zA-Z0-9+.-]*:/
const HOST_AND_PORT = /^[^/:\s]+:\d+(\/|$)/

export function safeUrl(value: string | null | undefined): string | null {
  const trimmed = value?.trim()
  if (!trimmed) return null
  // "javascript:alert(1)" has no "//", so "has a scheme" is decided by the
  // leading `name:`; a bare host (or host:port) gets https://.
  const candidate =
    !HAS_SCHEME.test(trimmed) || HOST_AND_PORT.test(trimmed) ? `https://${trimmed}` : trimmed
  let url: URL
  try {
    url = new URL(candidate)
  } catch {
    return null
  }
  if (!LINKABLE.has(url.protocol.toLowerCase())) return null
  if (url.protocol === 'mailto:') return url.pathname ? candidate : null
  return url.host ? candidate : null
}

/** 'https://www.linkedin.com/in/x/' -> 'linkedin.com/in/x' */
export function displayUrl(value: string): string {
  let shown = value.trim()
  for (const prefix of ['https://', 'http://', 'mailto:']) {
    if (shown.toLowerCase().startsWith(prefix)) shown = shown.slice(prefix.length)
  }
  if (shown.toLowerCase().startsWith('www.')) shown = shown.slice(4)
  return shown.replace(/\/+$/, '')
}

export interface ContactItem {
  text: string
  href: string | null
}

export function contactItems(info: {
  email: string
  phone: string | null
  location: string | null
  website: string | null
  github: string | null
  linkedin: string | null
}): ContactItem[] {
  const web = (value: string | null): ContactItem | null =>
    value?.trim() ? { text: displayUrl(value), href: safeUrl(value) } : null
  const items: (ContactItem | null)[] = [
    info.email ? { text: info.email, href: `mailto:${info.email}` } : null,
    info.phone ? { text: info.phone, href: null } : null,
    info.location ? { text: info.location, href: null } : null,
    web(info.website),
    web(info.github),
    web(info.linkedin),
  ]
  return items.filter((item): item is ContactItem => item !== null)
}
