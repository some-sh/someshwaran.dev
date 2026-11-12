import { expect, test, type Page } from '@playwright/test'

import { ADMIN_KEY } from '../testConfig'

const auth = { Authorization: `Bearer ${ADMIN_KEY}` }
const SHOTS = process.env.MOBILE_SHOTS

// Phone-width layout: nothing may force sideways scrolling, and the primary
// controls must stay reachable. Content is deliberately awkward (long unbroken
// strings, many items) because that is what breaks layouts, not a tidy demo.
const LONG = 'Averyveryverylongunbrokenwordthatwillnotwrapanywhereunlessthelayoutallowsit'

async function overflow(page: Page): Promise<number> {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
}

async function shot(page: Page, name: string) {
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true })
}

for (const width of [320, 375]) {
  test.describe(`at ${width}px wide`, () => {
    test.use({ viewport: { width, height: 800 }, hasTouch: true, isMobile: true })

    test('public, sign-in, list, editor and preview do not scroll sideways', async ({
      page,
      request,
    }) => {
      const name = `Mobile e2e ${width} ${LONG}`
      const created = await request.post('/api/admin/resumes', {
        headers: auth,
        data: {
          name,
          headline: `Senior SDET | Test Automation & Infrastructure | ${LONG}`,
          summary: `Summary ${LONG} `.repeat(3),
          personal_info: {
            full_name: 'Mobile Person',
            email: `${LONG}@example.com`,
            linkedin: `linkedin.com/in/${LONG}`,
            location: 'Chennai, India',
          },
          skills: Array.from({ length: 14 }, (_, i) => ({
            name: `Skill number ${i}`,
            category: i % 2 ? 'Languages and frameworks' : 'Test tools',
          })),
          experience: [
            {
              company: `Company ${LONG}`,
              role: `Role ${LONG}`,
              start_date: '2019-01-01',
              end_date: null,
              location: 'Chennai',
              highlights: [`Did a thing ${LONG}`, 'Did another thing'],
            },
          ],
          projects: [
            {
              name: `Project ${LONG}`,
              url: `https://example.com/${LONG}`,
              description: 'A project',
              tech_stack: ['Python', 'FastAPI', 'React', 'TypeScript', 'Playwright'],
            },
          ],
        },
      })
      expect(created.ok()).toBeTruthy()
      const id = (await created.json()).id as number

      try {
        // The public page only shows the default resume.
        const made = await request.post(`/api/admin/resumes/${id}/set-default`, { headers: auth })
        expect(made.ok()).toBeTruthy()
        await page.goto('/')
        await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
        await shot(page, `${width}-public`)
        expect(await overflow(page), 'public page').toBeLessThanOrEqual(0)

        await page.goto('/admin/login')
        await page.getByLabel('API key').fill(ADMIN_KEY)
        await shot(page, `${width}-login`)
        expect(await overflow(page), 'sign-in').toBeLessThanOrEqual(0)
        await page.getByRole('button', { name: 'Sign in' }).click()

        await expect(page.getByRole('heading', { name: 'Resumes' })).toBeVisible()
        await shot(page, `${width}-list`)
        expect(await overflow(page), 'resume list').toBeLessThanOrEqual(0)

        await page.goto(`/admin/resumes/${id}`)
        await expect(page.getByRole('heading', { name: 'Edit resume' })).toBeVisible()
        await shot(page, `${width}-editor`)
        expect(await overflow(page), 'editor').toBeLessThanOrEqual(0)

        await page.goto(`/admin/resumes/${id}/preview`)
        await expect(page.getByText(/^(Not published|Published \(default\))$/)).toBeVisible()
        await shot(page, `${width}-preview`)
        expect(await overflow(page), 'preview').toBeLessThanOrEqual(0)
      } finally {
        await request.delete(`/api/admin/resumes/${id}`, { headers: auth })
      }
    })
  })
}
