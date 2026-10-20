import { describe, expect, it } from 'vitest'
import { formatMoney, generateMessageId, truncate, cn } from './utils'

describe('formatMoney', () => {
  it('formats a whole number as INR currency', () => {
    expect(formatMoney(1000)).toBe('₹1,000.00')
  })

  it('formats a decimal value', () => {
    expect(formatMoney(1234.5)).toBe('₹1,234.50')
  })

  it('formats zero', () => {
    expect(formatMoney(0)).toBe('₹0.00')
  })
})

describe('generateMessageId', () => {
  it('returns a string starting with MSG-', () => {
    const id = generateMessageId()
    expect(id).toMatch(/^MSG-[0-9A-F]{14}$/)
  })

  it('returns unique ids on consecutive calls', () => {
    const a = generateMessageId()
    const b = generateMessageId()
    expect(a).not.toBe(b)
  })
})

describe('truncate', () => {
  it('returns the same string when under the limit', () => {
    expect(truncate('hello', 10)).toBe('hello')
  })

  it('truncates and appends ellipsis when over the limit', () => {
    expect(truncate('hello world', 5)).toBe('hello…')
  })

  it('handles empty string', () => {
    expect(truncate('', 5)).toBe('')
  })
})

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('a', 'b')).toBe('a b')
  })

  it('handles conditionals', () => {
    expect(cn('a', true && 'b', false && 'c')).toBe('a b')
  })
})