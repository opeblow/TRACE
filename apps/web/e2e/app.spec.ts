import { expect, test, type Page } from '@playwright/test'

const API = 'http://api.test'
const WALLET = '0x' + 'be04'.repeat(16)
const COUNTERPARTY = '0x' + 'e'.repeat(64)
const DIGEST = 'Gx' + 'A'.repeat(42)

const analysis = {
  wallet_id: '11111111-1111-1111-1111-111111111111',
  address: WALLET,
  snapshot: { balance: '370.289621451', balance_unit: 'SUI', fetched_at: '2026-10-30T16:00:00Z', network: 'mainnet', checkpoint_height: 339837738, sources: ['tatum_sui_grpc'], activity_count: 1 },
  analysis: {
    baseline: { status: 'established', sample_count: 16 },
    anomalies: [{
      type: 'unusual_sui_movement', severity: 'medium', severity_without_memory: 'medium', state: 'open', amount_sui: '16516.158645565',
      threshold_sui: '5000', transaction_digest: DIGEST, counterparty: COUNTERPARTY, direction: 'in',
      rationale: 'This incoming movement is 6.7 robust deviations above the typical incoming amount. This is an unusual-pattern signal, not evidence of malicious activity.',
      uncertainty: 0.59, confidence: 0.41,
      confidence_factors: ['16 incoming transfers in the baseline (sample factor 0.62)', '6.7 robust deviations above the typical incoming amount (separation 0.34)'],
      rule_version: 'amount-outlier-v2', memory_context: [], evidence: [{ ref: DIGEST, source: 'tatum_sui_grpc', timestamp: 1_700_000_000_000 }],
    }],
    anomaly_count: 1, status: 'complete', partial_reasons: [], rule_version: 'amount-outlier-v2',
  },
  activity: { items: [{ digest: DIGEST, timestamp_ms: 1_700_000_000_000, checkpoint: 1, status: 'success', direction: 'in', amount_sui: '16516.158645565', counterparty: COUNTERPARTY, counterparty_label: null }], has_more: false },
  memory: { status: 'none', message: 'No saved memories for this wallet yet.', namespace_ref: 'abc123', recalled_count: 0, changed_result: false, memories: [], effects: [], stateless: { anomalies: [] } },
  history: { saved: true, investigation_id: '11111111-1111-1111-1111-111111111111', durable: true },
}

async function mockApi(page: Page, options: { history?: 'list' | 'empty' | 'error'; analyze?: 'ok' | 'error' } = {}) {
  const calls: string[] = []
  await page.route(`${API}/**`, async route => {
    const url = new URL(route.request().url())
    calls.push(`${route.request().method()} ${url.pathname}`)
    if (url.pathname === '/api/v1/investigations') {
      if (options.history === 'error') return route.fulfill({ status: 503, json: { detail: 'unavailable' } })
      const investigations = options.history === 'list'
        ? [{ investigation_id: analysis.wallet_id, address: WALLET, created_at: '2026-10-30T16:00:00Z', anomaly_count: 1, highest_severity: 'medium', status: 'complete' }]
        : []
      return route.fulfill({ json: { durable: true, storage: 'postgresql', investigations } })
    }
    if (url.pathname === '/api/v1/wallets/analyze') {
      if (options.analyze === 'error') return route.fulfill({ status: 502, json: { detail: 'Wallet data provider is unavailable. Reference: req-123' } })
      return route.fulfill({ json: analysis })
    }
    return route.fulfill({ status: 404, json: { detail: 'Not Found' } })
  })
  return calls
}

test('landing page leads with the product and validates the address', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Understand what')
  await expect(page.getByRole('heading', { name: 'Evidence before confidence.' })).toBeVisible()
  const input = page.getByLabel('Sui wallet address').first()
  await input.fill('0x123')
  await input.press('Enter')
  await expect(page.getByRole('alert').first()).toContainText('64 hexadecimal')
  await input.fill(WALLET)
  await input.press('Enter')
  await expect(page).toHaveURL(/\/analyze\/?\?address=0x/)
  await expect(page.getByLabel('Sui wallet address')).toHaveValue(WALLET)
})

test('FAQ answers open from the keyboard', async ({ page }) => {
  await page.goto('/')
  const question = page.getByText('Do I need to connect my wallet?')
  await question.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByText('It never asks for a seed phrase or private key')).toBeVisible()
})

test('analyze shows recent investigations from the API', async ({ page }) => {
  await mockApi(page, { history: 'list' })
  await page.goto('/analyze')
  const history = page.getByRole('region', { name: 'Recent investigations' })
  await expect(history.getByText('1 finding · medium')).toBeVisible()
  await history.getByRole('button').first().click()
  await expect(page.getByLabel('Sui wallet address')).toHaveValue(WALLET)
})

test('analyze shows empty and error states for history', async ({ page }) => {
  await mockApi(page, { history: 'empty' })
  await page.goto('/analyze')
  await expect(page.getByText('No investigations yet in this workspace.')).toBeVisible()
  await page.unrouteAll()
  await mockApi(page, { history: 'error' })
  await page.reload()
  await expect(page.getByText('History is unavailable right now.')).toBeVisible()
})

test('a full analysis shows the finding with evidence and confidence', async ({ page }) => {
  const calls = await mockApi(page, { history: 'empty' })
  await page.goto('/analyze')
  await page.getByLabel('Sui wallet address').fill(WALLET)
  await page.getByRole('button', { name: 'Analyze wallet' }).click()
  await expect(page).toHaveURL(/\/wallet\/overview/)
  await expect(page.getByText('370.289621451 SUI')).toBeVisible()
  await expect(page.getByText('41%')).toBeVisible()
  await expect(page.getByText('16 incoming transfers in the baseline')).toBeVisible()
  await expect(page.getByRole('link', { name: /Open transaction evidence/ })).toHaveAttribute('href', `https://suiscan.xyz/mainnet/tx/${DIGEST}`)
  expect(calls).toContain('POST /api/v1/wallets/analyze')
})

test('provider errors are shown, not hidden', async ({ page }) => {
  await mockApi(page, { history: 'empty', analyze: 'error' })
  await page.goto('/analyze')
  await page.getByLabel('Sui wallet address').fill(WALLET)
  await page.getByRole('button', { name: 'Analyze wallet' }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'Wallet data provider' })).toContainText('Reference: req-123')
  await expect(page).toHaveURL(/\/analyze/)
})

test('no page scrolls sideways', async ({ page }) => {
  await mockApi(page, { history: 'list' })
  for (const path of ['/', '/analyze', '/alerts', '/memories', '/wallet/overview']) {
    await page.goto(path)
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    expect(overflow, path).toBeLessThanOrEqual(0)
  }
})
