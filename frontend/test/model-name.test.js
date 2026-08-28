// Tests for the model-name display cleaner in src/lib/model.js.
//
// Same arrangement as the other suites here: the module is import-free, so the
// bare node runner can load it. The cases that matter are the ones drawn from
// the live feed, where the brand was repeated inside the model in every shape a
// shop managed to produce.
//
// Run with `npm test`.

import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const { displayModelName } = await import('../src/lib/model.js')

describe('displayModelName', () => {
  test('strips a leading brand', () => {
    assert.equal(displayModelName('Trek', 'Trek Rail 9.9'), 'Rail 9.9')
  })

  test('strips a brand that sits after a year, keeping the year', () => {
    assert.equal(
      displayModelName('Scott', '2023 Scott Contessa Genius 920'),
      '2023 Contessa Genius 920',
    )
  })

  test('strips a brand repeated twice', () => {
    assert.equal(
      displayModelName('Scott', 'Scott 2023 Scott Contessa Genius 920'),
      '2023 Contessa Genius 920',
    )
  })

  test('handles a multi-word brand', () => {
    assert.equal(
      displayModelName('Santa Cruz', '2025 Santa Cruz Heckler SL 1 C Stout'),
      '2025 Heckler SL 1 C Stout',
    )
  })

  test('is case-insensitive against the shop spelling', () => {
    assert.equal(displayModelName('Merida', '24 MERIDA SCULTURA 9000'), '24 SCULTURA 9000')
  })

  test('tidies punctuation stranded by the removal', () => {
    assert.equal(displayModelName('Trek', 'Trek - Marlin 5'), 'Marlin 5')
  })

  test('leaves a model that does not name the brand untouched', () => {
    assert.equal(
      displayModelName('Giant', 'TCR Advanced SL Disc Frame and Fork'),
      'TCR Advanced SL Disc Frame and Fork',
    )
  })

  test('does not match the brand inside a larger word', () => {
    // "Liv" must not eat the "Liv" in "Livewire".
    assert.equal(displayModelName('Liv', 'Livewire Special'), 'Livewire Special')
  })

  test('falls back to the raw model when it was only the brand', () => {
    assert.equal(displayModelName('Trek', 'Trek'), 'Trek')
  })

  test('handles a missing or empty model', () => {
    assert.equal(displayModelName('Trek', ''), '')
    assert.equal(displayModelName('Trek', null), '')
    assert.equal(displayModelName('Trek', undefined), '')
  })

  test('handles a missing brand without throwing', () => {
    assert.equal(displayModelName('', 'Rail 9.9'), 'Rail 9.9')
    assert.equal(displayModelName(null, 'Rail 9.9'), 'Rail 9.9')
  })

  test('a brand with regex metacharacters does not throw or corrupt', () => {
    // A brand ending in punctuation has no clean word boundary to match on, so
    // the model may pass through unchanged. What matters is that the escaped
    // pattern is valid: no exception, and a real string back.
    assert.equal(typeof displayModelName('E+', 'E+ Explore Pro'), 'string')
  })
})
