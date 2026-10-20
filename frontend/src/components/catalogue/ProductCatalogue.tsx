import { useCallback, useState } from 'react'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { useCatalogue } from '@/hooks/useCatalogue'
import { ProductCard } from './ProductCard'
import type { Product } from '@/types'

interface ProductCatalogueProps {
  onAddToCart: (product: Product) => void
}

export function ProductCatalogue({ onAddToCart }: ProductCatalogueProps) {
  const { products, loading, error, reload, search } = useCatalogue()
  const [query, setQuery] = useState('')
  const [, setOpenProduct] = useState<string | null>(null)

  const filtered = search(query)

  const handleAdd = useCallback(
    (product: Product) => {
      onAddToCart(product)
    },
    [onAddToCart],
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-text tracking-tight">
            Product catalogue
          </h2>
          <p className="text-xs text-text-muted">
            Real stock and prices from the QuoteMate backend
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={reload} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </Button>
      </div>

      <div className="relative">
        <Input
          placeholder="Search by name, ID, or description…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {query && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setQuery('')}
            className="absolute right-2 top-1/2 -translate-y-1/2 h-8 px-2 text-xs"
          >
            Clear
          </Button>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-900/30 bg-red-900/10 p-3">
          <p className="text-xs text-red-300">Could not load catalogue: {error}</p>
        </div>
      )}

      <div
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
        aria-label="Catalogue products"
      >
        {loading && products.length === 0 ? (
          <div className="col-span-full">
            <SkeletonRow />
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No matching products"
            description="Try a different search term or refresh the catalogue."
          />
        ) : (
          filtered.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onAdd={handleAdd}
              onView={setOpenProduct}
              disabled={loading}
            />
          ))
        )}
      </div>
    </div>
  )
}

function SkeletonRow() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="panel-lift flex flex-col gap-3 p-4">
          <div className="aspect-video rounded-xl bg-surface-lift animate-pulse" />
          <div className="h-4 w-3/4 bg-surface-lift animate-pulse" />
          <div className="h-3 w-full bg-surface-lift animate-pulse" />
          <div className="h-4 w-1/2 bg-surface-lift animate-pulse" />
          <div className="h-8 w-full rounded-lg border border-border bg-surface-lift animate-pulse" />
        </div>
      ))}
    </div>
  )
}