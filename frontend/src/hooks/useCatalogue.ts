import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/apiClient'
import type { Product } from '@/types'

export function useCatalogue() {
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.products()
      setProducts(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load catalogue')
      setProducts([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const search = useCallback(
    (query: string) => {
      const q = query.toLowerCase().trim()
      if (!q) return products
      return products.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.id.toLowerCase().includes(q) ||
          p.description.toLowerCase().includes(q),
      )
    },
    [products],
  )

  return { products, loading, error, reload: load, search }
}