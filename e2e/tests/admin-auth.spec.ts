import { expect, test } from '@playwright/test'

import { ADMIN_KEY } from '../testConfig'

// Each test gets a fresh browser context (Playwright default), so none
// of these carry a stored admin key from a previous test.
test.describe('admin auth', () => {
  test('visiting an admin route without a key redirects to login', async ({ page }) => {
    await page.goto('/admin')

    await expect(page.getByText('Admin sign-in')).toBeVisible()
  })

  test('a wrong key shows an error and does not sign in', async ({ page }) => {
    await page.goto('/admin/login')
    await page.getByLabel('API key').fill('definitely-the-wrong-key')
    await page.getByRole('button', { name: 'Sign in' }).click()

    await expect(page.getByText('Invalid API key.')).toBeVisible()
    await expect(page).toHaveURL(/\/admin\/login$/)
  })

  test('the correct key signs in and reaches the resume list', async ({ page }) => {
    await page.goto('/admin/login')
    await page.getByLabel('API key').fill(ADMIN_KEY)
    await page.getByRole('button', { name: 'Sign in' }).click()

    await expect(page.getByRole('heading', { name: 'Resumes' })).toBeVisible()
  })
})
