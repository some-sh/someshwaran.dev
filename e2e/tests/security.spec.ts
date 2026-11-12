import { expect, test } from '@playwright/test'

import { ADMIN_KEY } from '../testConfig'

// A Content-Security-Policy that blocks the app's own scripts or styles would
// take the whole site down, and unit tests cannot see that: only a real
// browser enforcing the real policy against the real built app can. Every
// page below is loaded with a violation listener installed first.
test.describe('security headers and policy', () => {
  test('the page ships the headers on the HTML and on API responses', async ({ page }) => {
    const response = await page.goto('/')
    const headers = response!.headers()

    expect(headers['content-security-policy']).toContain("script-src 'self'")
    expect(headers['content-security-policy']).toContain("frame-ancestors 'none'")
    expect(headers['x-content-type-options']).toBe('nosniff')
    expect(headers['x-frame-options']).toBe('DENY')

    const api = await page.request.get('/api/admin/whoami')
    expect(api.headers()['cache-control']).toBe('no-store')
  })

  test('no CSP violation on the public page, sign-in, resume list or editor', async ({ page }) => {
    await page.addInitScript(() => {
      const w = window as unknown as { __csp: string[] }
      w.__csp = []
      document.addEventListener('securitypolicyviolation', (event) => {
        w.__csp.push(`${event.violatedDirective}: ${event.blockedURI || event.sample}`)
      })
    })
    const violations = () => page.evaluate(() => (window as unknown as { __csp: string[] }).__csp)

    await page.goto('/')
    // Either a published resume (heading) or the "nothing published yet" message,
    // depending on what earlier specs left in the database.
    await expect(
      page.getByRole('heading').first().or(page.getByText('No resume has been published yet.')),
    ).toBeVisible()
    expect(await violations()).toEqual([])

    await page.goto('/admin/login')
    await page.getByLabel('API key').fill(ADMIN_KEY)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByRole('heading', { name: 'Resumes' })).toBeVisible()
    expect(await violations()).toEqual([])

    await page.goto('/admin/resumes/new')
    await expect(page.getByRole('heading', { name: /new resume/i })).toBeVisible()
    expect(await violations()).toEqual([])
  })

  test('the interactive API docs are not exposed', async ({ request }) => {
    for (const path of ['/docs', '/redoc', '/openapi.json']) {
      expect((await request.get(path)).status(), path).toBe(404)
    }
  })
})
