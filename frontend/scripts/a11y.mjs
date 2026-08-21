/**
 * Every page, checked against the things that lock somebody out.
 *
 *   node scripts/a11y.mjs
 *
 * Not a full WCAG audit — those need a human. This catches the mechanical
 * failures that make a page unusable without a mouse or without sight, and that
 * nothing else here would notice: an input with no label, a button with no
 * accessible name, an image with no alt, a heading order that skips a level, a
 * control that cannot be reached by tab, and text too faint to read.
 */
import { chromium } from 'playwright'

// 8000 and 8010 are other projects on this machine. A wrong default here does
// not error -- it authenticates against a different app and then reports on it.
const API = process.env.API_URL ?? 'http://127.0.0.1:8020'
const APP = process.env.APP_URL ?? 'http://localhost:5173'
const EMAIL = `a11y${Date.now()}@example.com`, PW = 'screenshot-account-pw'

await fetch(`${API}/api/v1/auth/register`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: EMAIL, password: PW, name: 'A', phone: '+919000004321' }) })
const { access_token } = await (await fetch(`${API}/api/v1/auth/jwt/login`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ username: EMAIL, password: PW }) })).json()
const auth = { 'Content-Type': 'application/json', Authorization: `Bearer ${access_token}` }

await fetch(`${API}/api/v1/profile`, { method: 'PATCH', headers: auth, body: JSON.stringify({ annual_income: 2400000, monthly_expenses: 70000, is_salaried: true, years_to_goal: 15 }) })
const goal = await (await fetch(`${API}/api/v1/goals`, { method: 'POST', headers: auth, body: JSON.stringify({ goal_type: 'education', goal_name: "Daughter's college", target_amount: 6000000, current_savings: 300000, target_date: '2041-06-01', years: 15, risk_profile: 'moderate' }) })).json()
const h = await (await fetch(`${API}/api/v1/portfolio/holdings`, { method: 'POST', headers: auth, body: JSON.stringify({ asset_type: 'MF', identifier: '118955', name: 'HDFC Flexi Cap Fund - Growth Option - Regular Plan', category: 'Flexi Cap' }) })).json()
for (let i = 0; i < 6; i++) {
  await fetch(`${API}/api/v1/portfolio/holdings/${h.id}/transactions`, { method: 'POST', headers: auth, body: JSON.stringify({ txn_type: 'BUY', txn_date: new Date(Date.UTC(2023, i, 5)).toISOString().slice(0, 10), units: 15, price: 1400 }) })
}

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
  ['goals', '/goals'],
  ['goal', `/goals/${goal.id}`],
  ['profile', '/profile'],
  ['goal-new', '/goals/new'],
  ['login', '/login'],
]

const audit = () => {
  const problems = []
  const label = (el) =>
    (el.getAttribute('aria-label') ||
      el.getAttribute('title') ||
      (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent) ||
      el.closest('label')?.textContent ||
      el.textContent ||
      el.getAttribute('placeholder') ||
      '').trim()

  // Every control a person can reach must announce what it does.
  for (const el of document.querySelectorAll('button, a[href], select, textarea, input:not([type=hidden])')) {
    const r = el.getBoundingClientRect()
    if (r.width < 2 || r.height < 2) continue
    if (!label(el)) problems.push(`${el.tagName.toLowerCase()} with no accessible name — ${el.outerHTML.slice(0, 80)}`)
  }

  // A form field without a label is a field a screen reader cannot introduce.
  for (const el of document.querySelectorAll('input:not([type=hidden]), select, textarea')) {
    const r = el.getBoundingClientRect()
    if (r.width < 2 || r.height < 2) continue
    const labelled =
      el.getAttribute('aria-label') ||
      el.getAttribute('aria-labelledby') ||
      (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)) ||
      el.closest('label')
    if (!labelled) problems.push(`form field with no label — ${el.outerHTML.slice(0, 80)}`)
  }

  for (const img of document.querySelectorAll('img')) {
    if (img.alt === null || img.alt === undefined) problems.push(`img with no alt — ${img.src.slice(0, 60)}`)
  }

  // Heading levels are how a screen-reader user skims. Skipping one turns the
  // outline into a list.
  const levels = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map((h) => +h.tagName[1])
  for (let i = 1; i < levels.length; i++) {
    if (levels[i] - levels[i - 1] > 1) {
      problems.push(`heading jumps h${levels[i - 1]} → h${levels[i]}`)
      break
    }
  }
  if (levels.length && levels[0] !== 1) problems.push(`page starts at h${levels[0]}, not h1`)

  // Muted text is the usual place contrast quietly fails.
  //
  // Colours are read through a canvas rather than parsed. Chrome hands back
  // computed styles in whatever space they were authored in — this app is
  // written in oklch — and treating "oklch(0.505 0.014 265)" as three sRGB
  // channels produced a contrast reading of 1.07:1 for white text on a blue
  // button. The canvas always answers in sRGB, and it composites alpha for
  // free, which the backdrop-blurred header needs.
  const probe = document.createElement('canvas')
  probe.width = probe.height = 1
  const ctx2d = probe.getContext('2d', { willReadFrequently: true })
  const srgb = (color, under = 'rgb(255,255,255)') => {
    ctx2d.clearRect(0, 0, 1, 1)
    ctx2d.fillStyle = under
    ctx2d.fillRect(0, 0, 1, 1)
    ctx2d.fillStyle = color
    ctx2d.fillRect(0, 0, 1, 1)
    const [r, g, b] = ctx2d.getImageData(0, 0, 1, 1).data
    return [r, g, b]
  }
  const luminance = (rgb) => {
    const [r, g, b] = rgb.map((v) => {
      const s = v / 255
      return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
  }
  // Walk up compositing every translucent layer onto the page background, so a
  // header at 70% opacity is measured as what the eye actually sees.
  const pageBg = getComputedStyle(document.body).backgroundColor || 'rgb(255,255,255)'
  const effectiveBg = (el) => {
    const layers = []
    for (let n = el; n; n = n.parentElement) {
      const c = getComputedStyle(n).backgroundColor
      if (c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') layers.unshift(c)
    }
    let out = srgb(pageBg)
    for (const layer of layers) out = srgb(layer, `rgb(${out.join(',')})`)
    return out
  }

  const seen = new Set()
  for (const el of document.querySelectorAll('p, span, td, th, li, label, a, button, h1, h2, h3')) {
    if (!el.textContent?.trim() || el.children.length) continue
    const style = getComputedStyle(el)
    if (style.visibility === 'hidden' || style.display === 'none' || +style.opacity === 0) continue
    // Decoration is exempt under WCAG 1.4.3, and marking it aria-hidden is how
    // this codebase says so. Judging a bullet against body-text contrast would
    // push the design toward shouting every separator.
    if (el.closest('[aria-hidden="true"], [aria-hidden]')) continue
    const back = effectiveBg(el)
    const key = `${style.color}|${back.join(',')}|${style.fontSize}|${style.fontWeight}`
    if (seen.has(key)) continue
    seen.add(key)

    const size = parseFloat(style.fontSize)
    const bold = parseInt(style.fontWeight, 10) >= 700
    const large = size >= 24 || (size >= 18.66 && bold)
    const l1 = luminance(srgb(style.color, `rgb(${back.join(',')})`))
    const l2 = luminance(back)
    const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
    const needed = large ? 3 : 4.5
    if (ratio < needed - 0.05) {
      problems.push(
        `contrast ${ratio.toFixed(2)}:1 needs ${needed}:1 — "${el.textContent.trim().slice(0, 34)}" at ${Math.round(size)}px`,
      )
    }
  }
  return problems
}

const b = await chromium.launch()
let bad = 0
for (const theme of ['dark', 'light']) {
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: theme })
  await ctx.addInitScript(([t, j]) => {
    localStorage.setItem('nextrade-theme', t)
    localStorage.setItem('nextrade_token', j)
  }, [theme, access_token])

  for (const [name, path] of PAGES) {
    const p = await ctx.newPage()
    await p.goto(`${APP}${path}`, { waitUntil: 'networkidle' })
    await p.waitForTimeout(8000)
    const problems = await p.evaluate(audit)

    // And it must be reachable without a mouse at all.
    const focusable = await p.evaluate(
      () => document.querySelectorAll('button, a[href], select, textarea, input:not([type=hidden])').length,
    )
    if (focusable > 0) {
      let reached = 0
      for (let i = 0; i < Math.min(focusable + 4, 40); i++) {
        await p.keyboard.press('Tab')
        const on = await p.evaluate(() => document.activeElement?.tagName ?? '')
        if (on && on !== 'BODY') reached++
      }
      if (reached === 0) problems.push('nothing on this page can be reached with Tab')
    }

    if (problems.length) {
      bad++
      console.log(`\n${theme}/${name}:`)
      ;[...new Set(problems)].slice(0, 5).forEach((x) => console.log('   ' + x))
    }
    await p.close()
  }
  await ctx.close()
}
await b.close()
console.log(bad ? `\n${bad} page-theme combos with problems` : '\nevery page is usable without a mouse or sight')
process.exit(bad ? 1 : 0)
