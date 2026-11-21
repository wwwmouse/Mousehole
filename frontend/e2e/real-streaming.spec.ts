import { expect, test } from '@playwright/test'

/**
 * Optional real-model smoke test (skipped by default).
 * Requires the Docker stack at 8090 and a configured DeepSeek/Ollama provider.
 * Run with: $env:E2E_REAL_STREAMING=1; npx playwright test real-streaming
 */
test('assistant reply is rendered incrementally in the browser', async ({ page }) => {
  test.skip(
    !process.env.E2E_REAL_STREAMING,
    'set E2E_REAL_STREAMING=1 to run against a real provider',
  )

  const created = await page.request.post('/api/v1/tasks', {
    data: {
      title: 'SSE UI check ' + Date.now(),
      model_provider: 'deepseek',
      model_name: 'deepseek-flash',
    },
  })
  expect(created.ok()).toBeTruthy()
  const task = await created.json()

  await page.goto('/tasks/' + task.id)
  const composer = page.getByLabel('对话输入框')
  await expect(composer).toBeVisible()
  await composer.fill('请写一段大约 150 字的话：什么是确定性工作流。')
  await composer.press('Enter')

  const assistant = page.locator('.chat-message--assistant').last()
  const samples: number[] = []
  const deadline = Date.now() + 30_000
  let sawStreamingBubble = false
  while (Date.now() < deadline) {
    await page.waitForTimeout(100)
    const streaming = page.locator('.chat-message--assistant .spinner')
    if (await streaming.count()) sawStreamingBubble = true
    const text = await assistant.innerText().catch(() => '')
    samples.push(text.length)
    if (samples.length > 20) {
      const stable = samples.slice(-10)
      if (stable.every((value) => value === stable[0]) && sawStreamingBubble && stable[0] > 0) break
    }
  }
  console.log('samples:', JSON.stringify(samples))
  const distinct = new Set(samples.filter((value) => value > 0))
  console.log('distinct lengths:', distinct.size)
  expect(sawStreamingBubble).toBeTruthy()
  expect(distinct.size).toBeGreaterThan(2)
})
