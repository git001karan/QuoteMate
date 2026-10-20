import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useCatalogue } from './useCatalogue'

const originalFetch = globalThis.fetch

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  ;(globalThis as any).fetch = originalFetch
})

describe('useCatalogue', () => {
  it('loads products on mount', async () => {
    const mockData = [
      { id: 'p1', name: 'Widget', description: 'A widget', price: 100, stock: 10 },
    ]
    ;(globalThis.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockData,
    })

    const { result } = renderHook(() => useCatalogue())
    expect(result.current.loading).toBe(true)

    await act(async () => {
      await new Promise((r) => setTimeout(r, 0))
    })

    expect(result.current.products).toHaveLength(1)
    expect(result.current.products[0].name).toBe('Widget')
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('sets error when fetch fails', async () => {
    ;(globalThis.fetch as any).mockRejectedValueOnce(new Error('Network error'))

    const { result } = renderHook(() => useCatalogue())

    await act(async () => {
      await new Promise((r) => setTimeout(r, 0))
    })

    expect(result.current.error).toContain('Network error')
    expect(result.current.products).toHaveLength(0)
    expect(result.current.loading).toBe(false)
  })

  it('search filters products by name, id, or description', async () => {
    const mockData = [
      { id: 'p1', name: 'Mechanical Keyboard', description: 'Clicky keys', price: 5000, stock: 5 },
      { id: 'p2', name: 'Mouse', description: 'Wireless mouse', price: 1500, stock: 20 },
    ]
    ;(globalThis.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockData,
    })

    const { result } = renderHook(() => useCatalogue())

    await act(async () => {
      await new Promise((r) => setTimeout(r, 0))
    })

    expect(result.current.search('keyboard')).toHaveLength(1)
    expect(result.current.search('keyboard')[0].name).toBe('Mechanical Keyboard')
    expect(result.current.search('wireless')).toHaveLength(1)
    expect(result.current.search('wireless')[0].id).toBe('p2')
    expect(result.current.search('')).toHaveLength(2)
  })

  it('reload refetches products', async () => {
    const mockData = [
      { id: 'p1', name: 'Widget', description: 'A widget', price: 100, stock: 10 },
    ]
    ;(globalThis.fetch as any).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockData,
    })

    const { result } = renderHook(() => useCatalogue())

    await act(async () => {
      await new Promise((r) => setTimeout(r, 0))
    })

    expect(result.current.products).toHaveLength(1)

    // Reload should call fetch again
    await act(async () => {
      await result.current.reload()
    })

    expect(globalThis.fetch).toHaveBeenCalledTimes(2)
  })
})