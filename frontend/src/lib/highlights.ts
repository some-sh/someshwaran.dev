import type { Highlight } from './types'

/**
 * The editor edits an experience's bullets as plain text, one per line, with
 * an optional sub-heading syntax:
 *
 *   ## Release and installation quality     <- starts a group
 *   Automated release installation checks   <- bullets under it
 *   Owned release validation end to end
 *   ##                                      <- ends the group (bullets after are ungrouped)
 *
 * The API and database store structured ``{text, group}`` items; these two
 * functions convert between that and the text, so a user never edits JSON.
 */
const GROUP_MARKER = '##'

export function textToHighlights(text: string): Highlight[] {
  const result: Highlight[] = []
  let group: string | null = null
  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim()
    if (line === GROUP_MARKER || line.startsWith(`${GROUP_MARKER} `)) {
      group = line.slice(GROUP_MARKER.length).trim() || null
    } else if (line) {
      result.push({ text: line, group })
    }
  }
  return result
}

export function highlightsToText(highlights: Highlight[]): string {
  const lines: string[] = []
  let group: string | null = null
  for (const highlight of highlights) {
    if (highlight.group !== group) {
      lines.push(highlight.group ? `${GROUP_MARKER} ${highlight.group}` : GROUP_MARKER)
      group = highlight.group
    }
    lines.push(highlight.text)
  }
  return lines.join('\n')
}

/** Consecutive highlights with the same group, in order, for rendering. */
export function groupHighlights(
  highlights: Highlight[],
): { title: string | null; bullets: string[] }[] {
  const groups: { title: string | null; bullets: string[] }[] = []
  for (const highlight of highlights) {
    const last = groups.at(-1)
    if (last && last.title === highlight.group) {
      last.bullets.push(highlight.text)
    } else {
      groups.push({ title: highlight.group, bullets: [highlight.text] })
    }
  }
  return groups
}
