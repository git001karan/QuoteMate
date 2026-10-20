import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { api, ApiError, BASE } from './apiClient'

const originalFetch = globalThis.fetch

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  ;(globalThis as any).fetch = originalFetch
})

describe('apiClient BASE', () => {
  it('defaults to http://127.0.0.1:8000', () => {
    expect(BASE).toBe('http://127.0.0.1:8000')
  })
})

describe('api.health', () => {
  it('returns health data on success', async () => {
    const mockData = {
      status: 'ok',
      timestamp: '2026-01-01T00:00:00Z',
      service: 'quotemate',
      version: '1.0.0',
    }
    ;(globalThis.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockData,
    })

    const result = await api.health()
    expect(result.status).toBe('ok')
    expect(result.service).toBe('quotemate')
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/health',
      expect.objectContaining({
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
      }),
    )
  })

  it('throws ApiError on non-ok response', async () => {
    const mockedFetch = globalThis.fetch as unknown as { mockResolvedValueOnce: (val: unknown) => void }
    mockedFetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: async () => ({ detail: 'Service unavailable' }),
    })

    await expect(api.health()).rejects.toBeInstanceOf(ApiError)
  })
})

describe('api.products', () => {
  it('returns a list of products', async () => {
    const mockData = [
      { id: 'p1', name: 'Widget', description: 'A widget', price: 100, stock: 10 },
    ]
    ;(globalThis.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockData,
    })

    const result = await api.products()
    expect(result).toHaveLength(1)
    expect(result[0].name).toBe('Widget')
  })
})

describe('api.sendMessage', () => {
  it('posts a message and returns the reply', async () => {
    const mockReply = {
      message_id: 'MSG-ABCD1234',
      sender_id: 'customer_001',
      reply_text: 'Got it',
      duplicated: false,
      intent: 'cart.add',
      intent_confidence: 0.99,
      needs_clarification: false,
      is_unsupported: false,
      conversation_state: 'ACTIVE',
      cart: null,
      quotation_id: null,
      enquiry_id: null,
      quotation_status: null,
      quotation: null,
      stock_issues: [],
      handoff_id: null,
      handoff_status: null,
    }
    ;(globalThis.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockReply,
    })

    const result = await api.sendMessage({
      message_id: 'MSG-ABCD1234',
      sender_id: 'customer_001',
      text: 'add widget to cart',
      timestamp: '2026-01-01T00:00:00Z',
    })

    expect(result.reply_text).toBe('Got it')
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/messages',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})

describe('api.cart', () => {
  it('returns cart contents for a sender', async () => {
    const mockData = {
      sender_id: 'customer_001',
      items: [],
      subtotal: 0,
      is_empty: true,
    }
    ;(globalThis.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockData,
    })

    const result = await api.cart('customer_001')
    expect(result.sender_id).toBe('customer_001')
    expect(result.is_empty).toBe(true)
  })
})

describe('api.clearCart', () => {
  it('sends DELETE and returns confirmation', async () => {
    const mockData = { message: 'Cart cleared', sender_id: 'customer_001' }
    ;(globalThis.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockData,
    })

    const result = await api.clearCart('customer_001')
    expect(result.message).toBe('Cart cleared')
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/cart/customer_001',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })
})

describe('api.conversations', () => {
  it('returns a list of conversations', async () => {
    const mockData = [
      {
        sender_id: 'customer_001',
        state: 'ACTIVE',
        pending_product_id: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ]
    ;(globalThis.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockData,
    })

    const result = await api.conversations()
    expect(result).toHaveLength(1)
    expect(result[0].sender_id).toBe('customer_001')
  })
})