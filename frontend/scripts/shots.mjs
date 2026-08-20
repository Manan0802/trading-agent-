/**
 * Screenshots every page in both themes, with a seeded account, so UI changes
 * can actually be looked at instead of assumed. Run against a live dev server:
 *
 *   node scripts/shots.mjs [outDir]
 */
import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'

const APP = process.env.APP_URL ?? 'http://localhost:5173'
// 8000 is another project on this machine. Defaulting there produced a token
// this app rejects, so every page silently screenshotted the login screen and
// the run still reported success.
const API = process.env.API_URL ?? 'http://127.0.0.1:8020'
const OUT = process.argv[2] ?? 'shots'

const EMAIL = `shots+${Date.now()}@example.com`
const PASSWORD = 'screenshot-account-pw'

async function seed() {
  await fetch(`${API}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: EMAIL, password: PASSWORD, name: 'Shots', phone: '+919000000001' }),
  })
  const form = new URLSearchParams({ username: EMAIL, password: PASSWORD })
  const res = await fetch(`${API}/api/v1/auth/jwt/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form,
  })
  const body = await res.json()
  const token = body.access_token
  if (!token) {
    // Without this the run writes a folder of login screens and calls it done.
    console.error(
      `could not authenticate against ${API} (HTTP ${res.status}). ` +
        `Screenshots would all be the login page. Set API_URL if the backend is elsewhere.`,
    )
    process.exit(1)
  }
  const auth = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }

  const goal = await (
    await fetch(`${API}/api/v1/goals`, {
      method: 'POST',
      headers: auth,
      body: JSON.stringify({
        goal_type: 'education',
        goal_name: "Daughter's college",
        target_amount: 4000000,
        current_savings: 250000,
        target_date: '2041-06-01',
        years: 15,
        risk_profile: 'moderate',
      }),
    })
  ).json()

  // A real SIP history so the portfolio page has XIRR to show rather than zeroes.
  const holding = await (
    await fetch(`${API}/api/v1/portfolio/holdings`, {
      method: 'POST',
      headers: auth,
      body: JSON.stringify({
        asset_type: 'MF',
        identifier: '122639',
        name: 'Parag Parikh Flexi Cap Fund Direct Growth',
        category: 'Flexi Cap',
      }),
    })
  ).json()

  for (let i = 0; i < 14; i += 1) {
    const d = new Date(Date.UTC(2024, 3 + i, 5))
    await fetch(`${API}/api/v1/portfolio/holdings/${holding.id}/transactions`, {
      method: 'POST',
      headers: auth,
      body: JSON.stringify({
        txn_type: 'BUY',
        txn_date: d.toISOString().slice(0, 10),
        units: 15000 / (68 + i * 1.4),
        price: 68 + i * 1.4,
      }),
    })
  }

  return { token, goalId: goal.id }
}

const { token, goalId } = await seed()

const PAGES = [
  ['portfolio', '/portfolio'],
  ['research', '/research'],
  ['screener', '/screener'],
  ['screener-all', '/screener?view=all'],
  ['profile', '/profile'],
  ['goals', '/goals'],
  ['goal-new', '/goals/new'],
  ['goal-detail', `/goals/${goalId}`],
  ['login', '/login'],
]

await mkdir(OUT, { recursive: true })
const browser = await chromium.launch()

for (const theme of ['light', 'dark']) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    deviceScaleFactor: 2,
    colorScheme: theme,
  })
  await context.addInitScript(
    ([t, jwt]) => {
      localStorage.setItem('nextrade-theme', t)
      localStorage.setItem('nextrade_token', jwt)
    },
    [theme, token],
  )

  for (const [name, path] of PAGES) {
    const page = await context.newPage()
    const errors = []
    page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
    page.on('pageerror', (e) => errors.push(String(e)))
    await page.goto(`${APP}${path}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1200)
    await page.screenshot({ path: `${OUT}/${name}-${theme}.png`, fullPage: true })
    if (errors.length) console.log(`! ${name}-${theme}:`, errors.slice(0, 3).join(' | '))
    await page.close()
  }
  await context.close()
}

await browser.close()
console.log(`wrote ${PAGES.length * 2} screenshots to ${OUT}/`)
