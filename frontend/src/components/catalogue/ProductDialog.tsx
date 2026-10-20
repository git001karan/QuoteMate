import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/apiClient'
import { formatMoney } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Dialog } from '@/components/ui/Dialog'
import type { Product } from '@/types'

interface ProductDialogProps {
  productId: string | null
  open: boolean
  onClose: () => void
  onAddToCart: (product: Product) => void
}

export function ProductDialog({
  productId,
  open,
  onClose,
  onAddToCart,
}: ProductDialogProps) {
  const [product, setProduct] = useState<Product | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!productId || !open) return
    setLoading(true)
    try {
      setProduct(await api.product(productId))
    } catch {
      onClose()
    } finally {
      setLoading(false)
    }
  }, [productId, open, onClose])

  useEffect(() => {
    load()
  }, [load])

  if (!open) return null

  return (
    <Dialog open={open} onOpenChange={(v) => v || onClose()} title="Product details">
      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <span className="animate-pulse flex h-8 w-24 rounded-full bg-surface-lift" />
        </div>
      ) : product ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-surface-lift p-4">
            <p className="text-xs text-text-muted uppercase tracking-wider font-semibold mb-1">
              {product.id}
            </p>
            <h3 className="text-base font-semibold text-text">{product.name}</h3>
            <p className="text-sm text-text-muted">{product.description}</p>
            <div className="mt-3 flex items-center gap-3">
              <span className="text-sm font-semibold text-text">{formatMoney(product.price)}</span>
              <Badge
                variant={
                  product.stock === 0
                    ? 'destructive'
                    : product.stock < 10
                      ? 'warning'
                      : 'success'
                }
              >
                {product.stock === 0 ? 'Out of stock' : product.stock < 10 ? 'Low stock' : 'In stock'}
              </Badge>
            </div>
          </div>
          <Button
            variant="violet"
            onClick={() => {
              onAddToCart(product)
              onClose()
            }}
            disabled={product.stock === 0}
            className="w-full"
          >
            {product.stock === 0 ? 'Out of stock' : `Add 1 × ${product.name} to cart`}
          </Button>
        </div>
      ) : null}
    </Dialog>
  )
}