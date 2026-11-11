/**
 * WashMate – silent Playwright demonstration (student + operator workflows on the REAL app).
 *
 *   1. Start a fresh isolated instance:   bash demo/serve-demo.sh      (separate terminal)
 *   2. Record:                            node tests/e2e/demo.spec.js
 *
 * Output: demo/washmate-demo.mp4 (H.264, NO audio track) + demo/screenshots/*.png
 *
 * Only dedicated TEST accounts and a fake UPI ID / transaction reference are used.
 * The 15-minute reminder is produced by the app's own reminder logic (not faked): a test booking that starts
 * ~16 minutes from now is created through the API and the script waits until the reminder is generated.
 */
import { chromium, request } from 'playwright'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const BASE = process.env.DEMO_BASE_URL || 'http://127.0.0.1:4173'
const STUDENT = { email: process.env.DEMO_STUDENT_EMAIL || 'demo.student@washmate.test', password: process.env.DEMO_STUDENT_PASSWORD || 'DemoStudent#2026' }
const OPERATOR = { email: process.env.DEMO_OPERATOR_EMAIL || 'operator@washmate.test', password: process.env.DEMO_OPERATOR_PASSWORD || 'DemoOperator#2026' }
const OUT_DIR = path.join(ROOT, 'demo')
const SHOTS = path.join(OUT_DIR, 'screenshots')
const RAW = path.join(OUT_DIR, 'raw')
fs.mkdirSync(SHOTS, { recursive: true })
fs.rmSync(RAW, { recursive: true, force: true })
fs.mkdirSync(RAW, { recursive: true })

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const pad = (n) => String(n).padStart(2, '0')
const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

// ------------------------------------------------------------------ 1. API preparation (not recorded)
async function prepare() {
  const api = await request.newContext({ baseURL: BASE })
  const post = async (c, url, data, method = 'post') => {
    const r = await c[method](url, { data })
    if (!r.ok()) throw new Error(`${method.toUpperCase()} ${url} -> ${r.status()} ${await r.text()}`)
    return r.json()
  }
  await post(api, '/api/auth/login', { ...OPERATOR, portal: 'OPERATOR' })
  // Demo-only operator configuration: round-the-clock hours + 5-minute grid so a near-term slot always exists.
  await post(api, '/api/settings', { open_time: '00:00', close_time: '23:59', slot_interval_minutes: 5 }, 'patch')
  const serverNow = new Date((await (await api.get('/api/health')).json()).time)
  const start = new Date(serverNow.getTime() + 16 * 60000)
  start.setMinutes(Math.ceil(start.getMinutes() / 5) * 5, 0, 0)
  if (ymd(start) !== ymd(serverNow)) throw new Error('Run the demo earlier than 23:30 server time.')
  const modes = (await (await api.get('/api/wash-modes')).json()).wash_modes
  const normal = modes.find((m) => m.name === 'Normal Wash')

  const stu = await request.newContext({ baseURL: BASE })
  await post(stu, '/api/auth/login', { ...STUDENT, portal: 'STUDENT' })
  const { booking } = await post(stu, '/api/bookings', { wash_mode_id: normal.id, booking_date: ymd(start), start_time: `${pad(start.getHours())}:${pad(start.getMinutes())}` })
  await post(stu, '/api/payments/submit', { booking_id: booking.id, transaction_reference: 'DEMOSETUP0001' })
  const pend = (await (await api.get('/api/payments/pending')).json()).payments
  await post(api, `/api/payments/${pend.find((p) => p.booking_id === booking.id).id}/verify`, undefined, 'patch')
  // A pending rescheduling request for the operator to review later in the video
  const tomorrow = new Date(serverNow.getTime() + 86400000)
  await post(stu, '/api/reschedule', { booking_id: booking.id, requested_date: ymd(tomorrow), requested_start_time: '14:00', reason: 'Demo: lab session at that time' })

  console.log(`Prepared test booking ${booking.start_time} today; waiting for the real 15-minute reminder (up to ~7 min)…`)
  for (let i = 0; i < 90; i++) {
    const n = (await (await stu.get('/api/notifications')).json()).notifications
    if (n.some((x) => x.notification_type === 'REMINDER')) { console.log('Reminder generated.'); break }
    if (i === 89) throw new Error('Reminder was not generated in time')
    await sleep(5000)
  }
  await api.dispose(); await stu.dispose()
  return { tomorrow: ymd(tomorrow) }
}

// ------------------------------------------------------------------ 2. recorded session
const CURSOR_JS = `
  (() => {
    const make = () => {
      if (document.getElementById('wm-cursor')) return
      const c = document.createElement('div'); c.id = 'wm-cursor'
      c.style.cssText = 'position:fixed;z-index:2147483647;pointer-events:none;left:0;top:0;width:22px;height:22px;transform:translate(-3px,-2px);'
      c.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22"><path d="M3 2l7 18 2.6-7.4L20 10z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>'
      document.documentElement.appendChild(c)
      const pos = JSON.parse(sessionStorage.getItem('wm-pos') || '[640,360]')
      c.style.left = pos[0] + 'px'; c.style.top = pos[1] + 'px'
      window.addEventListener('mousemove', (e) => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; sessionStorage.setItem('wm-pos', JSON.stringify([e.clientX, e.clientY])) }, true)
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', make); else make()
  })()`

async function record({ tomorrow }) {
  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: RAW, size: { width: 1280, height: 720 } }, acceptDownloads: true, locale: 'en-IN' })
  await ctx.addInitScript(CURSOR_JS)
  const p = await ctx.newPage()
  const problems = []
  p.on('pageerror', (e) => problems.push(e.message))
  p.on('console', (m) => m.type() === 'error' && !/401/.test(m.text()) && problems.push(m.text()))
  let x = 640, y = 360

  const glide = async (loc) => {
    await loc.waitFor({ state: 'visible', timeout: 20000 })
    await loc.scrollIntoViewIfNeeded()
    const b = await loc.boundingBox()
    const tx = b.x + b.width / 2 + (Math.random() * 6 - 3), ty = b.y + b.height / 2 + (Math.random() * 4 - 2)
    const steps = Math.max(20, Math.min(45, Math.round(Math.hypot(tx - x, ty - y) / 14)))
    await p.mouse.move(tx, ty, { steps })
    x = tx; y = ty
    await sleep(350)
  }
  const click = async (loc, after = 900) => { await glide(loc); await loc.click(); await sleep(after) }
  const type = async (loc, text) => { await click(loc, 200); await loc.pressSequentially(text, { delay: 70 }); await sleep(400) }
  const shot = (name) => p.screenshot({ path: path.join(SHOTS, `${name}.png`) })
  const nav = (name) => click(p.getByRole('link', typeof name === 'string' ? { name, exact: true } : { name }), 1400)
  const hold = (ms) => sleep(ms)

  await p.goto(BASE + '/')
  await p.mouse.move(x, y)
  await hold(2500); await shot('01-landing')

  // ---------------- Student ----------------
  await click(p.getByRole('link', { name: /Student login/ }))
  await type(p.locator('input[name=email]'), STUDENT.email)
  await type(p.locator('input[name=password]'), STUDENT.password)
  await shot('02-student-login')
  await click(p.getByRole('button', { name: 'Sign in' }), 1800)
  await p.getByText('Your next appointment').waitFor()
  await hold(2500); await shot('03-student-dashboard')

  await click(p.getByRole('link', { name: 'Book a wash', exact: true }), 1500)
  await click(p.getByRole('button', { name: /Heavy Wash/ }), 1800)
  await hold(1500); await shot('04-book-mode')
  await click(p.locator('div.overflow-x-auto > button').nth(1), 1800)   // tomorrow
  const slot = p.locator('button[aria-label="10:00 AM available"]')
  await click(slot, 1200)
  await hold(2200); await shot('05-book-review')
  await click(p.getByRole('button', { name: /Reserve & continue to payment/ }), 1800)
  await p.getByTestId('upi-id').waitFor()
  await hold(2800); await shot('06-payment-instructions')
  await type(p.getByPlaceholder(/e\.g\. 412/), 'DEMOTEST000001')
  await click(p.getByRole('button', { name: 'Submit for verification' }), 1800)
  await p.getByText('Waiting for operator verification').waitFor()
  await hold(2200); await shot('07-payment-submitted')

  await nav('My Bookings')
  await hold(1800)
  await click(p.getByRole('button', { name: 'Details' }).first(), 1500)
  await hold(2200); await shot('08-booking-details')
  await click(p.getByRole('button', { name: 'Close' }), 800)
  await nav(/^Notifications/)  // accessible name includes the unread badge
  await p.getByText('Appointment reminder').first().waitFor()
  await hold(3000); await shot('09-notifications-reminder')
  await click(p.getByRole('button', { name: 'Log out' }), 1500)

  // ---------------- Operator ----------------
  await p.goto(BASE + '/')
  await hold(800)
  await click(p.getByRole('link', { name: /Operator login/ }))
  await type(p.locator('input[name=email]'), OPERATOR.email)
  await type(p.locator('input[name=password]'), OPERATOR.password)
  await click(p.getByRole('button', { name: 'Sign in' }), 1800)
  await p.getByText('Upcoming appointments').waitFor()
  await hold(2800); await shot('10-operator-overview')

  await nav('Machines')
  await hold(2200); await shot('11-machines')
  const m3 = p.getByTestId('machine-M3')
  await click(m3.getByRole('button', { name: /Maintenance/ }), 1000)
  await type(p.getByRole('dialog').locator('textarea'), 'Demo: drum noise (test data)')
  await click(p.getByRole('button', { name: 'Mark as under maintenance' }), 1800)
  await hold(1800); await shot('12-machine-maintenance')
  await click(m3.getByRole('button', { name: /Restore/ }), 1800)

  await nav('Wash Modes')
  await hold(1800)
  await click(p.locator('tr', { hasText: 'Quick Wash' }).getByRole('button', { name: /Edit/ }), 1200)
  await hold(2500); await shot('13-wash-mode-config')
  await click(p.getByRole('button', { name: 'Close' }), 900)

  await nav('Payments')
  await p.getByText('DEMOTEST000001').waitFor()
  await hold(2500); await shot('14-payments-pending')
  await click(p.locator('tr', { hasText: 'DEMOTEST000001' }).getByRole('button', { name: /Verify/ }), 1200)
  await hold(1500)
  await click(p.getByRole('button', { name: 'Yes, payment received' }), 2000)
  await shot('15-payment-verified')

  await nav('Appointments')
  await hold(2200); await shot('16-appointments-table')
  await click(p.getByRole('button', { name: /Daily schedule/ }), 1800)
  await hold(2000); await shot('17-daily-schedule')
  await click(p.getByRole('button', { name: /Calendar/ }), 1800)
  await hold(2000)

  await nav('Rescheduling')
  await p.getByText('Demo: lab session').waitFor()
  await hold(2200)
  await click(p.getByRole('button', { name: /Check/ }), 1500)
  await shot('18-rescheduling')
  await click(p.locator('tr', { hasText: 'Demo: lab session' }).getByRole('button', { name: /Approve/ }), 1200)
  await click(p.getByRole('dialog').getByRole('button', { name: 'Approve', exact: true }), 2000)

  await nav('Reports')
  // the demo bookings now sit on tomorrow's date, so show that day's report
  await glide(p.locator('input[type=date]')); await p.locator('input[type=date]').fill(tomorrow); await sleep(1200)
  await p.getByText('Appointment demand by hour').waitFor()
  await hold(3000); await shot('19-reports-daily')
  await click(p.getByRole('button', { name: /Weekly/ }), 2200)
  await click(p.getByRole('button', { name: /Export CSV/ }), 2000)
  await hold(1500)
  await click(p.getByRole('button', { name: 'Log out' }), 2000)

  const video = p.video()
  await ctx.close(); await browser.close()
  const webm = await video.path()
  if (problems.length) console.warn('Browser console problems:', problems)
  return webm
}

// ------------------------------------------------------------------ 3. encode + verify
function encode(webm) {
  const mp4 = path.join(OUT_DIR, 'washmate-demo.mp4')
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', webm, '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '23', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4])
  const probe = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', mp4]).toString())
  const kinds = probe.streams.map((s) => s.codec_type)
  console.log('MP4 streams:', kinds.join(','), '| duration:', Number(probe.format.duration).toFixed(1), 's | size:', (probe.format.size / 1e6).toFixed(2), 'MB')
  if (kinds.includes('audio')) throw new Error('Audio stream present!')
  if (!kinds.includes('video')) throw new Error('No video stream!')
  return mp4
}

const prep = await prepare()
const webm = await record(prep)
encode(webm)
fs.rmSync(RAW, { recursive: true, force: true })
console.log('Demo video written to demo/washmate-demo.mp4')
