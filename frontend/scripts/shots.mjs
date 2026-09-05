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

  // Four holdings, not one. This used to seed a single direct-plan equity
  // fund, and a single direct-plan equity fund is the one portfolio in which
  // half of `/portfolio` renders nothing: no second fund means no overlap
  // panel, no stock means no filings and no excluded-holding note on the
  // chart, and no REGULAR plan means the cost review says "nothing to fix".
  // Every screenshot this harness has ever written was of a page missing four
  // of its panels -- which is precisely the state it exists to catch.
  const FIXTURE = [
    // The regular plan. The only reason CostReview has a number at all.
    { identifier: '125494', name: 'SBI Small Cap Fund - Regular Plan - Growth',
      asset_type: 'MF', category: 'Small Cap', units: 7.5, price0: 130, step: 2.6 },
    { identifier: '122639', name: 'Parag Parikh Flexi Cap Fund - Direct Plan - Growth',
      asset_type: 'MF', category: 'Flexi Cap', units: 25, price0: 60, step: 1.2 },
    { identifier: '119533', name: 'Aditya Birla Sun Life Corporate Bond Fund - Growth - Direct Plan',
      asset_type: 'MF', category: 'Corporate Bond', units: 33.33, price0: 24, step: 0.48 },
    // A stock, so the filings panel and the chart's funds-only note both render.
    { identifier: 'TATASTEEL.NS', name: 'Tata Steel Ltd.',
      asset_type: 'STOCK', category: null, units: 16.67, price0: 130, step: 2.6 },
  ]

  // A real SIP history so the portfolio page has XIRR to show rather than zeroes.
  for (const f of FIXTURE) {
    const holding = await (
      await fetch(`${API}/api/v1/portfolio/holdings`, {
        method: 'POST',
        headers: auth,
        body: JSON.stringify({
          asset_type: f.asset_type,
          identifier: f.identifier,
          name: f.name,
          category: f.category,
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
          units: f.units,
          price: f.price0 + i * f.step,
        }),
      })
    }
  }

  return { token, goalId: goal.id }
}

const { token, goalId } = await seed()

const PAGES = [
  ['portfolio', '/portfolio'],
  ['research', '/research'],
  ['decide', '/decide'],
  ['screener', '/screener'],
  ['screener-all', '/screener?view=all'],
  ['screener-stocks', '/screener?tab=stocks'],
  ['screener-basket', '/screener?tab=basket'],
  ['fund', '/screener/fund/122639'],
  ['stock', '/screener/stock/HDFCBANK.NS'],
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
    // Scroll the whole page and come back. Anything revealed by an
    // IntersectionObserver has never intersected in a fresh tab, so a
    // fullPage screenshot of it is a picture of empty bands -- the capture
    // reaches past the viewport, the observer does not.
    await page.evaluate(async () => {
      const step = window.innerHeight * 0.8
      for (let y = 0; y < document.body.scrollHeight; y += step) {
        window.scrollTo(0, y)
        await new Promise((r) => setTimeout(r, 60))
      }
      window.scrollTo(0, 0)
    })
    // Three seconds, not one: most of these pages read a rate-limited "heavy"
    // endpoint, the limit is 20 a minute per user, and one account shoots every
    // page in both themes. At 1.2s the run fitted two dozen heavy calls into
    // half a minute and whichever page came last got a 429 -- so the harness
    // wrote a screenshot of an error panel and reported success, which is the
    // exact failure this file exists to prevent.
    await page.waitForTimeout(3000)
    await page.screenshot({ path: `${OUT}/${name}-${theme}.png`, fullPage: true })
    if (errors.length) console.log(`! ${name}-${theme}:`, errors.slice(0, 3).join(' | '))
    await page.close()
  }
  await context.close()
}

// Signed out, in its own context. `/` renders the landing page only when
// there is no token, so shooting it in the authenticated pass above would
// silently capture a redirect to the dashboard.
for (const theme of ['light', 'dark']) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    deviceScaleFactor: 2,
    colorScheme: theme,
  })
  await context.addInitScript((t) => localStorage.setItem('nextrade-theme', t), theme)
  const page = await context.newPage()
  const errors = []
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
  page.on('pageerror', (e) => errors.push(String(e)))
  await page.goto(`${APP}/`, { waitUntil: 'networkidle' })
  await page.evaluate(async () => {
    const step = window.innerHeight * 0.8
    for (let y = 0; y < document.body.scrollHeight; y += step) {
      window.scrollTo(0, y)
      await new Promise((r) => setTimeout(r, 60))
    }
    window.scrollTo(0, 0)
  })
  await page.waitForTimeout(1200)
  await page.screenshot({ path: `${OUT}/landing-${theme}.png`, fullPage: true })
  // And the hero at viewport size. Chromium's stitched fullPage capture drops
  // the `preserve-3d` card stack -- it is on the page, correctly transformed
  // and fully opaque (checked via getBoundingClientRect and getComputedStyle),
  // but composites out of the expanded capture. Without this second shot the
  // harness produces a picture of an empty hero and looks like a bug report.
  await page.screenshot({ path: `${OUT}/landing-hero-${theme}.png` })
  if (errors.length) console.log(`! landing-${theme}:`, errors.slice(0, 3).join(' | '))
  await context.close()
}

await browser.close()
console.log(`wrote ${PAGES.length * 2 + 4} screenshots to ${OUT}/`)
