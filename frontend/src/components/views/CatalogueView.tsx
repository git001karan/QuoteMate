import { useCallback } from 'react'
import { ProductCatalogue } from '@/components/catalogue/ProductCatalogue'
import type { Product } from '@/types'

interface CatalogueViewProps {
  senderId: string
  onAddToCart: (product: Product) => void
}

export function CatalogueView({ senderId, onAddToCart }: CatalogueViewProps) {
  const handleAdd = useCallback(
    async (product: Product) => {
      try {
        await onAddToCart(product)
      } catch {
        // Errors are surfaced by the caller via toasts
      }
    },
    [onAddToCart],
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-text tracking-tight">
          Catalogue — {senderId}
        </h2>
        <span className="text-xs text-text-muted">
          Add items to your cart; they appear in the workspace for confirmation.
        </span>
      </div>
      <ProductCatalogue onAddToCart={handleAdd} />
    </div>
  )
}