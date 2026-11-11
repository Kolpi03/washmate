import test from 'node:test'
import assert from 'node:assert/strict'
import { addDays, inr, statusText, t12 } from '../../frontend/src/utils/format.js'

test('t12 converts 24h to 12h clock', () => {
  assert.equal(t12('00:05'), '12:05 AM')
  assert.equal(t12('09:30'), '9:30 AM')
  assert.equal(t12('12:00'), '12:00 PM')
  assert.equal(t12('18:45'), '6:45 PM')
  assert.equal(t12(null), '—')
})

test('addDays crosses month and year boundaries', () => {
  assert.equal(addDays('2026-11-30', 1), '2026-12-01')
  assert.equal(addDays('2026-12-31', 1), '2027-01-01')
  assert.equal(addDays('2026-03-01', -1), '2026-02-28')
})

test('inr and statusText', () => {
  assert.equal(inr(30), '₹30')
  assert.equal(inr(null), '₹0')
  assert.equal(statusText('PAYMENT_SUBMITTED'), 'Awaiting verification')
  assert.equal(statusText('COMPLETED'), 'Completed')
})
