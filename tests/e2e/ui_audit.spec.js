/**
 * UI audit against a LOCAL demo instance (never production):
 *   bash demo/serve-demo.sh            # terminal 1 (fresh throw-away DB)
 *   node tests/e2e/ui_audit.spec.js    # terminal 2
 */
import { chromium, request } from 'playwright'

const BASE = process.env.DEMO_BASE_URL || 'http://127.0.0.1:4173'
if (!/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(BASE)) { console.error('Refusing to audit a non-local URL'); process.exit(2) }
const OP = { email: 'operator@washmate.test', password: process.env.DEMO_OPERATOR_PASSWORD || 'DemoOperator#2026' }
const ST = { email: 'demo.student@washmate.test', password: 'DemoStudent#2026' }
const pad = (n) => String(n).padStart(2, '0')
let pass = 0, fail = 0
const ok = (name, cond, extra = '') => { cond ? pass++ : fail++; console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : '  -> ' + extra}`) }

// ---------- API setup ----------
const api = await request.newContext({ baseURL: BASE })
const post = async (c, url, data, m = 'post') => { const r = await c[m](url, { data }); if (!r.ok()) throw new Error(`${url} ${r.status()} ${await r.text()}`); return r.json() }
await post(api, '/api/auth/login', { ...OP, portal: 'OPERATOR' })
await post(api, '/api/settings', { open_time: '00:00', close_time: '23:59', slot_interval_minutes: 5 }, 'patch')
const now = new Date((await (await api.get('/api/health')).json()).time)
const when = new Date(now.getTime() + 60 * 60000); when.setMinutes(Math.ceil(when.getMinutes() / 5) * 5, 0, 0)
const sameDay = when.getDate() === now.getDate()
const stu = await request.newContext({ baseURL: BASE })
await post(stu, '/api/auth/login', { ...ST, portal: 'STUDENT' })
const modes = (await (await stu.get('/api/wash-modes')).json()).wash_modes
const date = `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}`
if (!sameDay) throw new Error('Run before 23:00 server time')
const { booking } = await post(stu, '/api/bookings', { wash_mode_id: modes[1].id, booking_date: date, start_time: `${pad(when.getHours())}:${pad(when.getMinutes())}` })
await post(stu, '/api/payments/submit', { booking_id: booking.id, transaction_reference: 'AUDITTEST0001' })

const browser = await chromium.launch()
const login = async (p, who, portal) => {
  await p.goto(BASE + (portal === 'OPERATOR' ? '/operator/login' : '/login'))
  await p.locator('input[name=email]').fill(who.email); await p.locator('input[name=password]').fill(who.password)
  await p.keyboard.press('Enter')   // keyboard submit
  await p.waitForURL(portal === 'OPERATOR' ? '**/operator' : '**/student')
}

// ---------- 1. protected routes ----------
{
  const p = await (await browser.newContext()).newPage()
  await p.goto(BASE + '/student/bookings'); await p.waitForURL('**/login'); ok('anonymous /student/bookings -> /login', true)
  await p.goto(BASE + '/operator/payments'); await p.waitForURL('**/operator/login'); ok('anonymous /operator/payments -> /operator/login', true)
  await login(p, ST, 'STUDENT')
  await p.goto(BASE + '/operator/payments'); await p.waitForURL('**/student'); ok('student blocked from operator UI', true)
  await p.close()
}

// ---------- 2. forms ----------
{
  const p = await (await browser.newContext()).newPage()
  await p.goto(BASE + '/login'); await p.locator('input[name=email]').fill('nobody@x.io'); await p.locator('input[name=password]').fill('wrongpass1')
  await p.getByRole('button', { name: 'Sign in' }).click()
  ok('invalid login shows an alert', await p.getByRole('alert').filter({ hasText: /Invalid credentials/ }).isVisible())
  await p.goto(BASE + '/register'); await p.locator('input[type=password]').fill('short')
  const invalid = await p.locator('input[type=password]').evaluate((e) => !e.validity.valid)
  ok('register: short password blocked by validation', invalid)
  await p.close()
}

// ---------- 3. mobile layout: no horizontal page overflow ----------
const routes = { STUDENT: ['', '/book', '/bookings', '/notifications', '/profile', `/payment/${booking.id}`], OPERATOR: ['', '/appointments', '/payments', '/machines', '/modes', '/reschedules', '/reports', '/notifications', '/settings'] }
for (const [role, who] of [['STUDENT', ST], ['OPERATOR', OP]]) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } }); const p = await ctx.newPage()
  const errors = []; p.on('pageerror', (e) => errors.push(e.message)); p.on('console', (m) => m.type() === 'error' && !/401/.test(m.text()) && errors.push(m.text()))
  await login(p, who, role)
  for (const r of routes[role]) {
    const url = `${BASE}/${role.toLowerCase()}${r}`
    await p.goto(url); await p.waitForLoadState('networkidle'); await p.waitForTimeout(500)
    const m = await p.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, h1: document.querySelectorAll('h1').length,
      unnamedBtn: [...document.querySelectorAll('button,a')].filter((e) => !(e.innerText || e.getAttribute('aria-label') || e.title || '').trim()).length,
      unlabelled: [...document.querySelectorAll('input:not([type=hidden]),select,textarea')].filter((e) => !(e.closest('label') || e.getAttribute('aria-label') || (e.id && document.querySelector(`label[for="${e.id}"]`)))).length,
      imgNoAlt: [...document.querySelectorAll('img')].filter((e) => !e.hasAttribute('alt')).length }))
    ok(`mobile 390px ${role} ${r || '/'}: no horizontal overflow`, m.sw <= m.cw + 1, `scrollWidth ${m.sw} > ${m.cw}`)
    ok(`a11y ${role} ${r || '/'}: one h1, named controls, labelled inputs, img alt`, m.h1 === 1 && m.unnamedBtn === 0 && m.unlabelled === 0 && m.imgNoAlt === 0, JSON.stringify(m))
  }
  ok(`${role}: no console/page errors across pages`, errors.length === 0, errors.join(' | '))
  await ctx.close()
}

// ---------- 4. operator notification centre receives the student's payment alert ----------
const octx = await browser.newContext({ viewport: { width: 1280, height: 720 } }); const op = await octx.newPage()
await login(op, OP, 'OPERATOR')
await op.getByRole('link', { name: /^Notifications/ }).click(); await op.waitForURL('**/operator/notifications')
ok('operator can open Notifications and sees "Payment awaiting verification"', await op.getByText('Payment awaiting verification').first().isVisible())

// ---------- 5. double-click protection on Verify ----------
await op.goto(BASE + '/operator/payments'); await op.getByText('AUDITTEST0001').waitFor()
let verifyCalls = 0
op.on('request', (r) => { if (/\/payments\/\d+\/verify/.test(r.url()) && r.method() === 'PATCH') verifyCalls++ })
await op.locator('tr', { hasText: 'AUDITTEST0001' }).getByRole('button', { name: /Verify/ }).click()
const confirmBtn = op.getByRole('button', { name: 'Yes, payment received' })
await confirmBtn.dblclick({ delay: 10 }).catch(() => {})
await op.waitForTimeout(1500)
ok('double-clicking "Yes, payment received" sends exactly one verify request', verifyCalls === 1, `calls=${verifyCalls}`)

// ---------- 6. modal keyboard: Escape closes, focus stays in dialog ----------
await op.goto(BASE + '/operator/appointments'); await op.getByRole('button', { name: 'Manage' }).first().click()
ok('booking dialog opens with role=dialog', await op.getByRole('dialog').isVisible())
await op.keyboard.press('Escape'); await op.waitForTimeout(300)
ok('Escape closes the dialog', !(await op.getByRole('dialog').isVisible().catch(() => false)))

// ---------- 7. double-click on student "Reserve" creates one booking ----------
const sctx = await browser.newContext({ viewport: { width: 1280, height: 720 } }); const sp = await sctx.newPage()
await login(sp, ST, 'STUDENT')
await sp.goto(BASE + '/student/book'); await sp.getByRole('button', { name: /Quick Wash/ }).click()
await sp.locator('div.overflow-x-auto > button').nth(1).click()
await sp.locator('button[aria-label$="available"]').nth(100).click()
let created = 0
sp.on('request', (r) => { if (r.method() === 'POST' && /\/api\/bookings$/.test(r.url())) created++ })
await sp.getByRole('button', { name: /Reserve & continue/ }).dblclick({ delay: 10 }).catch(() => {})
await sp.waitForURL('**/payment/*'); await sp.waitForTimeout(800)
ok('double-clicking Reserve creates a single booking request', created === 1, `requests=${created}`)

await browser.close(); await api.dispose(); await stu.dispose()
console.log(`\n${pass} passed, ${fail} failed`)
process.exit(fail ? 1 : 0)
