import { expect, test } from '@playwright/test'

import { installMockApi } from './mockApi'

test('home renders combined overview with switchable charts', async ({ page }) => {
  await installMockApi(page)
  await page.goto('/')
  await expect(page.locator('.overview-panel--chart')).toBeVisible()
  await expect(page.locator('.bar-chart')).toHaveCount(1)
  await expect(page.locator('.bar-chart__bar')).toHaveCount(7)
  await expect(page.locator('.overview-panel--activity')).toBeVisible()
  await expect(page.locator('.activity-list__value')).toHaveCount(3)
  await page.getByRole('tab', { name: 'Token' }).click()
  await expect(page.locator('.bar-chart__bar')).toHaveCount(7)
  // Internal usage-completeness details must not be exposed to users.
  await expect(page.getByText('数据不完整')).toHaveCount(0)
  await page.screenshot({ path: 'test-results/home-stats.png', fullPage: true })
})

test('global tasks page is reachable from navigation', async ({ page }) => {
  await installMockApi(page)
  await page.goto('/')
  await page.getByRole('link', { name: 'Tasks' }).click()
  await expect(page).toHaveURL(/\/tasks$/)
  await expect(page.getByRole('heading', { name: 'Tasks' })).toBeVisible()
  await expect(page.getByRole('button', { name: '新建 Task' }).first()).toBeVisible()
  await page.getByRole('button', { name: '筛选' }).click()
  await expect(page.getByText('Project 内 Task')).toBeVisible()
  await expect(page.getByText('全局 Task')).toBeVisible()
  await page.getByRole('button', { name: '清空筛选' }).click()
})

test('core closed loop: upload file -> create project -> task -> chat -> artifact', async ({
  page,
}) => {
  await installMockApi(page)

  // 1) Upload a file into the Global Library.
  await page.goto('/library')
  await expect(page.getByRole('heading', { name: 'Library' })).toBeVisible()
  await page.locator('input[type="file"]').setInputFiles({
    name: 'e2e-notes.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# E2E Notes\n\nMock content'),
  })
  await expect(
    page.locator('.cell-file__name', { hasText: 'e2e-notes.md' }),
  ).toBeVisible()

  // 2) Create a Project and open it.
  await page.goto('/projects')
  await page.getByRole('button', { name: '新建 Project' }).first().click()
  await page.getByPlaceholder('例如：Agent Learning').fill('E2E Project')
  await page.getByRole('button', { name: '创建项目' }).click()
  const projectCard = page.locator('.project-card__name', { hasText: 'E2E Project' })
  await expect(projectCard).toBeVisible()
  await projectCard.click()

  // Project Overview is the default tab.
  await expect(page.getByText('最近活动')).toBeVisible()

  // 3) Create a Task from the project and send a chat message.
  await page.getByRole('tab').filter({ hasText: 'Tasks' }).click()
  await page.getByRole('button', { name: '新建 Task' }).first().click()

  // File content is readable directly from Task Settings.
  await page.getByRole('tab').filter({ hasText: 'Settings' }).click()
  await page.locator('.file-item__main--button').first().click()
  const previewDialog = page.getByRole('dialog')
  await expect(previewDialog).toContainText('E2E Notes')
  await page.keyboard.press('Escape')
  await page.getByRole('tab').filter({ hasText: 'Chat' }).click()

  const composer = page.getByLabel('对话输入框')
  await expect(composer).toBeVisible()
  await composer.fill('请生成一份 E2E 测试成果')
  await composer.press('Enter')

  // Mock SSE returns an artifact and a normal assistant reply.
  await expect(page.getByText('这是 Mock 生成的核心闭环成果。')).toBeVisible()
  await expect(page.getByText('思路链')).toBeVisible()
  await expect(page.locator('.artifact-receipt')).toContainText('本轮生成了 1 个成果')

  // 4) Open Artifacts from the receipt, preview and download the artifact.
  await page.getByRole('button', { name: '查看成果' }).click()
  await expect(page.locator('.artifacts-series__title', { hasText: 'E2E 系列' })).toBeVisible()
  await expect(
    page.locator('.artifacts-preview__title', { hasText: 'E2E 成果' }),
  ).toBeVisible()

  // Artifact can jump back to the exact chat turn that produced it.
  await page.getByRole('button', { name: '查看来源消息' }).click()
  await expect(page.locator('.chat-message--highlight')).toContainText(
    '这是 Mock 生成的核心闭环成果。',
  )
  await page.getByRole('tab').filter({ hasText: 'Artifacts' }).click()

  const actions = page.locator('.artifacts-preview__actions')
  const downloadPromise = page.waitForEvent('download')
  await actions.getByRole('button', { name: '下载' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('e2e-artifact.md')

  // 5) Delete the artifact version (mock) and confirm the empty state.
  await actions.getByRole('button', { name: '删除' }).click()
  const dialog = page.getByRole('dialog', { name: '删除成果版本' })
  await dialog.getByRole('button', { name: '删除' }).click()
  await expect(page.getByText('还没有成果')).toBeVisible()
})
