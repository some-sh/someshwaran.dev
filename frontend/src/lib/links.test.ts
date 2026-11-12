import { describe, expect, it } from 'vitest'

import { contactItems, displayUrl, safeUrl } from './links'

// Same table as backend/tests/unit/test_resume_document.py: the page, PDF and
// DOCX must agree on what is a safe link.
describe('safeUrl', () => {
  it.each([
    ['https://example.com/a', 'https://example.com/a'],
    ['http://example.com', 'http://example.com'],
    ['linkedin.com/in/someone', 'https://linkedin.com/in/someone'],
    ['example.com:8080/x', 'https://example.com:8080/x'],
    ['mailto:a@example.com', 'mailto:a@example.com'],
    ['javascript:alert(1)', null],
    ['JAVASCRIPT:alert(1)', null],
    ['data:text/html,<script>1</script>', null],
    ['file:///etc/passwd', null],
    ['ftp://example.com/x', null],
    ['https://', null],
    ['', null],
    ['   ', null],
    [null, null],
  ])('safeUrl(%j) -> %j', (value, expected) => {
    expect(safeUrl(value)).toBe(expected)
  })
})

describe('displayUrl', () => {
  it('drops scheme, www and trailing slash', () => {
    expect(displayUrl('https://www.linkedin.com/in/someone/')).toBe('linkedin.com/in/someone')
    expect(displayUrl('http://example.com')).toBe('example.com')
    expect(displayUrl('someshwaran.dev')).toBe('someshwaran.dev')
  })
})

describe('contactItems', () => {
  const info = {
    email: 'ada@example.com',
    phone: null,
    location: 'London',
    website: 'javascript:alert(1)',
    github: 'github.com/ada',
    linkedin: 'https://www.linkedin.com/in/ada',
  }

  it('links the email and safe URLs, and shows unsafe ones as plain text', () => {
    expect(contactItems(info)).toEqual([
      { text: 'ada@example.com', href: 'mailto:ada@example.com' },
      { text: 'London', href: null },
      { text: 'javascript:alert(1)', href: null },
      { text: 'github.com/ada', href: 'https://github.com/ada' },
      { text: 'linkedin.com/in/ada', href: 'https://www.linkedin.com/in/ada' },
    ])
  })
})
