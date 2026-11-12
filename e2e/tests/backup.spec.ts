import { readFile } from 'node:fs/promises'

import { expect, test } from '@playwright/test'

import { ADMIN_KEY } from '../testConfig'

const auth = { Authorization: `Bearer ${ADMIN_KEY}` }

// The point of a backup is surviving the loss of the database, so this proves
// the whole loop in a real browser: a resume exists, the downloaded file is
// kept, the resume is destroyed, and restoring from that file brings it back.
test('download a backup, lose the resume, restore it from the file', async ({ page, request }) => {
  const name = `Backup e2e ${Date.now()}`
  const created = await request.post('/api/admin/resumes', {
    headers: auth,
    data: {
      name,
      headline: 'Senior SDET',
      personal_info: { full_name: 'Ada Lovelace', email: 'ada@example.com' },
      skills: [{ name: 'Python' }],
    },
  })
  expect(created.ok()).toBeTruthy()
  const id = (await created.json()).id as number
  const cleanup: number[] = [id]

  try {
    await page.goto('/admin/login')
    await page.getByLabel('API key').fill(ADMIN_KEY)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByRole('link', { name })).toBeVisible()

    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Download backup' }).click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toMatch(/^someshwaran-backup-\d{4}-\d{2}-\d{2}\.json$/)
    const file = await download.path()
    const backup = JSON.parse(await readFile(file, 'utf8'))
    expect(backup.format).toBe('someshwaran.dev/resume-backup')
    expect(backup.resumes.map((r: { name: string }) => r.name)).toContain(name)

    // Disaster: the resume is gone.
    expect((await request.delete(`/api/admin/resumes/${id}`, { headers: auth })).ok()).toBeTruthy()
    await page.reload()
    await expect(page.getByRole('link', { name })).toHaveCount(0)

    // Restore from the very file that was downloaded.
    await page.getByLabel('Backup file').setInputFiles(file)
    await expect(page.getByRole('status')).toContainText(/restored/i)
    await expect(page.getByRole('link', { name })).toBeVisible()

    // Restoring the same file again is harmless: it is skipped, not duplicated.
    await page.getByLabel('Backup file').setInputFiles(file)
    await expect(page.getByRole('status')).toContainText(/skipped/i)
    await expect(page.getByRole('link', { name })).toHaveCount(1)
  } finally {
    const all = await (await request.get('/api/admin/resumes', { headers: auth })).json()
    for (const resume of all as { id: number; name: string }[]) {
      if (resume.name === name) cleanup.push(resume.id)
    }
    for (const resumeId of new Set(cleanup)) {
      await request.delete(`/api/admin/resumes/${resumeId}`, { headers: auth })
    }
  }
})
