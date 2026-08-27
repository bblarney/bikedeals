// Tests for the freshness labels in src/lib/time.js.
//
// Same arrangement as the other suites here: the module is import-free, so the
// bare node runner can load it. The cases that matter are the boundaries, since
// the whole point of the change was that calendar days, not elapsed hours,
// decide whether something reads as "today".
//
// Run with `npm test`.

import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const { formatDayLabel, formatShortDate } = await import('../src/lib/time.js')

// Local time deliberately: the labels are read by a person in their own
// timezone, and that is the boundary they experience.
const at = (y, m, d, h = 12, min = 0) => new Date(y, m - 1, d, h, min)

function daysAgo(n, h = 12) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  d.setHours(h, 0, 0, 0)
  return d
}

describe('formatDayLabel', () => {
  test('this morning is today', () => {
    assert.equal(formatDayLabel(daysAgo(0, 6)), 'today')
  })

  test('late last night is yesterday, not a few hours ago', () => {
    // The whole reason for calendar days: at 1am, 11pm last night is two hours
    // back but it is not today, and calling it "2h ago" hides that.
    assert.equal(formatDayLabel(daysAgo(1, 23)), 'yesterday')
  })

  test('two days back is a date', () => {
    const label = formatDayLabel(daysAgo(2))
    assert.notEqual(label, 'today')
    assert.notEqual(label, 'yesterday')
    assert.match(label, /^\d{1,2} [A-Z][a-z]{2}$/)
  })

  test('a clock skew into the future still reads as today', () => {
    const soon = new Date(Date.now() + 60_000)
    assert.equal(formatDayLabel(soon), 'today')
  })
})

describe('formatShortDate', () => {
  test('omits the year within the current one', () => {
    const thisYear = new Date().getFullYear()
    assert.equal(formatShortDate(at(thisYear, 6, 20)), '20 Jun')
  })

  test('includes the year once it is not the current one', () => {
    const older = new Date().getFullYear() - 2
    assert.equal(formatShortDate(at(older, 6, 20)), `20 Jun ${older}`)
  })
})
