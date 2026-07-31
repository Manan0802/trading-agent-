/**
 * Every page on a phone, in both a small iPhone and a Pixel.
 *
 *   node scripts/mobile.mjs
 *
 * Two failures, both invisible at 1440 and both found here the first time it
 * ran: the document scrolling sideways, and a control too small to hit with a
 * thumb. The header alone was pushing 555px of content through a 390px screen,
 * which meant every page in the app scrolled horizontally on the device most
 * Indian users would open it on.
 *
 * A wide table inside an overflow-x-auto box is contained, not a leak, so the
 * culprit search walks past those — otherwise the holdings table masks whatever
 * is really overflowing.
 */
import { chromium, devices } from 'playwright'
// 8000 and 8010 are other projects on this machine. A wrong default here does
// not error -- it authenticates against a different app and then reports on it.
const API = process.env.API_URL ?? 'http://127.0.0.1:8020'
const APP = process.env.APP_URL ?? 'http://localhost:5173'
const EMAIL = `mb${Date.now()}@example.com`, PW = 'screenshot-account-pw'

await fetch(`${API}/api/v1/auth/register`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: EMAIL, password: PW, name: 'M', phone: '+919000006666' }) })
const { access_token } = await (await fetch(`${API}/api/v1/auth/jwt/login`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ username: EMAIL, password: PW }) })).json()
const auth = { 'Content-Type': 'application/json', Authorization: `Bearer ${access_token}` }

await fetch(`${API}/api/v1/profile`, { method: 'PATCH', headers: auth, body: JSON.stringify({ annual_income: 2400000, monthly_expenses: 70000, is_salaried: true, years_to_goal: 15 }) })
const goal = await (await fetch(`${API}/api/v1/goals`, { method: 'POST', headers: auth, body: JSON.stringify({ goal_type: 'education', goal_name: "Daughter's college", target_amount: 6000000, current_savings: 300000, target_date: '2041-06-01', years: 15, risk_profile: 'moderate' }) })).json()
const h = await (await fetch(`${API}/api/v1/portfolio/holdings`, { method: 'POST', headers: auth, body: JSON.stringify({ asset_type: 'MF', identifier: '118955', name: 'HDFC Flexi Cap Fund - Growth Option - Regular Plan', category: 'Flexi Cap' }) })).json()
for (let i = 0; i < 8; i++) {
  await fetch(`${API}/api/v1/portfolio/holdings/${h.id}/transactions`, { method: 'POST', headers: auth, body: JSON.stringify({ txn_type: 'BUY', txn_date: new Date(Date.UTC(2023, i, 5)).toISOString().slice(0, 10), units: 15, price: 1400 }) })
}

const PAGES = [
  ['portfolio', '/portfolio'],
  ['research', '/research'],
  ['goals', '/goals'],
  ['goal', `/goals/${goal.id}`],
  ['profile', '/profile'],
  ['goal-new', '/goals/new'],
  ['login', '/login'],
]

const b = await chromium.launch()
let bad = 0
for (const [deviceName, descriptor] of [['iPhone 13', devices['iPhone 13']], ['Pixel 7', devices['Pixel 7']]]) {
  const ctx = await b.newContext({ ...descriptor, colorScheme: 'dark' })
  await ctx.addInitScript((j) => localStorage.setItem('nextrade_token', j), access_token)
  for (const [name, path] of PAGES) {
    const p = await ctx.newPage()
    const problems = []
    p.on('pageerror', (e) => problems.push('PAGEERROR ' + String(e).slice(0, 100)))
    p.on('console', (m) => m.type() === 'error' && problems.push('CONSOLE ' + m.text().slice(0, 100)))
    await p.goto(`${APP}${path}`, { waitUntil: 'networkidle' })
    await p.waitForTimeout(7000)

    const overflow = await p.evaluate(() => {
      const doc = document.documentElement
      const spill = doc.scrollWidth - doc.clientWidth
      if (spill <= 1) return null
      // Name the widest offender so the fix has somewhere to start.
      // Skip anything living inside a deliberate horizontal scroller: a wide
      // table in an overflow-x-auto box is contained, not a leak.
      const contained = (el) => {
        for (let n = el.parentElement; n; n = n.parentElement) {
          const ox = getComputedStyle(n).overflowX
          if (ox === 'auto' || ox === 'scroll') return true
        }
        return false
      }
      const worst = [...document.querySelectorAll('body *')]
        .map((el) => ({ el, r: el.getBoundingClientRect() }))
        .filter(({ el, r }) => r.right > doc.clientWidth + 1 && r.width > 0 && !contained(el))
        .sort((a, b) => b.r.right - a.r.right)[0]
      return {
        spill,
        culprit: worst
          ? `${worst.el.tagName.toLowerCase()}.${String(worst.el.className).split(' ').slice(0, 3).join('.')} → ${Math.round(worst.r.right)}px`
          : 'unknown',
      }
    })
    if (overflow) problems.push(`OVERFLOW ${overflow.spill}px past the viewport — ${overflow.culprit}`)

    // A tap target under 32px square is a miss on a phone.
    const small = await p.evaluate(() =>
      [...document.querySelectorAll('button, a[href], select, input')]
        .map((el) => ({ t: el.tagName.toLowerCase(), r: el.getBoundingClientRect(), x: (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 24) }))
        .filter(({ r }) => r.width > 2 && r.height > 2 && (r.height < 32 || r.width < 32))
        .map(({ t, r, x }) => `${t}"${x}" ${Math.round(r.width)}x${Math.round(r.height)}`)
        .slice(0, 4),
    )
    if (small.length) problems.push(`SMALL TAP TARGETS ${small.join(', ')}`)

    if (problems.length) {
      bad++
      console.log(`\n${deviceName}/${name}:`)
      problems.slice(0, 4).forEach((x) => console.log('   ' + x))
    }
    await p.close()
  }
  await ctx.close()
}
await b.close()
console.log(bad ? `\n${bad} page-device combos with problems` : '\nevery page fits a phone')
process.exit(bad ? 1 : 0)
