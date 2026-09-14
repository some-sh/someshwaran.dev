import { type Page, expect, test } from '@playwright/test'

import { ADMIN_KEY } from '../testConfig'

async function signIn(page: Page): Promise<void> {
  await page.goto('/admin/login')
  await page.getByLabel('API key').fill(ADMIN_KEY)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Resumes' })).toBeVisible()
}

// One continuous journey rather than independent tests: every step
// shares the same global state (the DB, and in particular the single
// "default resume" flag), so the steps only make sense run in this
// order. test.step() keeps each part separately reported without
// splitting them into tests that would race each other.
test('create, publish, clone, and delete a resume', async ({ page }) => {
  await test.step('public page has nothing published yet', async () => {
    await page.goto('/')
    await expect(page.getByText('No resume has been published yet.')).toBeVisible()
  })

  await test.step('sign in as admin', async () => {
    await signIn(page)
  })

  await test.step('create a resume', async () => {
    await page.getByRole('link', { name: 'New resume' }).click()
    await expect(page.getByRole('heading', { name: 'New resume' })).toBeVisible()

    await page.getByLabel('Internal name').fill('E2E Test Resume')
    await page.getByLabel('Full name').fill('Grace Hopper')
    await page.getByLabel('Email', { exact: true }).fill('grace@example.com')

    await page.getByRole('button', { name: 'Add skill' }).click()
    await page.getByLabel('Name', { exact: true }).fill('COBOL')

    await page.getByRole('button', { name: 'Save' }).click()
    await expect(page.getByRole('heading', { name: 'Edit resume' })).toBeVisible()
  })

  await test.step('a freshly created resume is not public yet', async () => {
    await page.goto('/')
    await expect(page.getByText('No resume has been published yet.')).toBeVisible()
  })

  await test.step('set it as default from the resume list', async () => {
    await page.goto('/admin')
    const row = page.locator('tr', { hasText: 'E2E Test Resume' })
    await row.getByRole('button', { name: 'Set default' }).click()
    // exact: true so this only matches the "Default" badge, not a
    // "Set default" button that might still be visible mid-transition.
    await expect(row.getByText('Default', { exact: true })).toBeVisible()
  })

  await test.step('the public page now renders it', async () => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Grace Hopper' })).toBeVisible()
    await expect(page.getByText('COBOL')).toBeVisible()
    await expect(page.getByRole('link', { name: 'Download PDF' })).toBeVisible()
  })

  await test.step('clone it', async () => {
    await page.goto('/admin')
    const originalRow = page.locator('tr', { hasText: 'E2E Test Resume' }).first()
    await originalRow.getByRole('button', { name: 'Clone' }).click()

    const cloneRow = page.locator('tr', { hasText: 'E2E Test Resume (copy)' })
    await expect(cloneRow).toBeVisible()
    // Cloning never inherits default status, even from the default resume.
    // exact: true matters here — getByText does a case-insensitive substring
    // match by default, which would also match the row's own "Set default"
    // button.
    await expect(cloneRow.getByText('Default', { exact: true })).toHaveCount(0)
  })

  await test.step('delete the clone', async () => {
    page.once('dialog', (dialog) => dialog.accept())
    const cloneRow = page.locator('tr', { hasText: 'E2E Test Resume (copy)' })
    await cloneRow.getByRole('button', { name: 'Delete' }).click()

    await expect(page.locator('tr', { hasText: 'E2E Test Resume (copy)' })).toHaveCount(0)
  })

  await test.step('delete the original, leaving no default resume', async () => {
    page.once('dialog', (dialog) => dialog.accept())
    const row = page.locator('tr', { hasText: 'E2E Test Resume' })
    await row.getByRole('button', { name: 'Delete' }).click()

    await expect(page.getByText('No resumes yet')).toBeVisible()
  })

  await test.step('public page is back to nothing published', async () => {
    await page.goto('/')
    await expect(page.getByText('No resume has been published yet.')).toBeVisible()
  })
})
