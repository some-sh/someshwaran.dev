import { expect, test } from '@playwright/test'

import { ADMIN_KEY } from '../testConfig'

const auth = { Authorization: `Bearer ${ADMIN_KEY}` }

// The reason the preview exists: look at a draft that is NOT the published
// resume, without publishing it. So this also proves it never leaks publicly.
test('preview an unpublished resume from the list without publishing it', async ({
  page,
  request,
}) => {
  const stamp = Date.now()
  const name = `Draft e2e ${stamp}`
  const headline = `Draft headline ${stamp}`
  const created = await request.post('/api/admin/resumes', {
    headers: auth,
    data: {
      name,
      headline,
      personal_info: { full_name: 'Preview Person', email: 'preview@example.com' },
      skills: [{ name: 'Python' }],
    },
  })
  expect(created.ok()).toBeTruthy()
  const id = (await created.json()).id as number

  try {
    await page.goto('/admin/login')
    await page.getByLabel('API key').fill(ADMIN_KEY)
    await page.getByRole('button', { name: 'Sign in' }).click()

    const row = page.getByRole('listitem').filter({ has: page.getByRole('link', { name }) })
    await row.getByRole('link', { name: 'Preview', exact: true }).click()

    await expect(page).toHaveURL(new RegExp(`/admin/resumes/${id}/preview$`))
    await expect(page.getByRole('heading', { name: 'Preview Person' })).toBeVisible()
    await expect(page.getByText(headline)).toBeVisible()
    await expect(page.getByText('Not published')).toBeVisible()

    // The draft must not have become public.
    const pub = await request.get('/api/resumes/default')
    if (pub.ok()) expect((await pub.json()).name).not.toBe(name)

    // And the way back to editing works from the preview.
    await page.getByRole('link', { name: 'Edit' }).click()
    await expect(page.getByRole('heading', { name: 'Edit resume' })).toBeVisible()
  } finally {
    await request.delete(`/api/admin/resumes/${id}`, { headers: auth })
  }
})
