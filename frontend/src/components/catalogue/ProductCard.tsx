import { ArrowRight } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { formatMoney } from '@/lib/utils'
import type { Product } from '@/types'

interface ProductCardProps {
  product: Product
  onAdd: (product: Product) => void
  onView?: (productId: string) => void
  disabled?: boolean
}

const stockIcon = (stock: number) => {
  if (stock === 0) return <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
  if (stock < 10) return <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
  return <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
}

export function ProductCard({
  product,
  onAdd,
  onView,
  disabled = false,
}: ProductCardProps) {
  return (
    <article
      className="panel-lift flex flex-col hover:border-violet/30 transition-colors group"
    >
      <div className="flex flex-col gap-3">
        <div className="aspect-video rounded-xl border border-border bg-surface flex items-center justify-center text-text-muted">
          <div className="w-10 h-10 rounded-full bg-violet/10 flex items-center justify-center text-violet-200 font-mono text-xs font-bold">
            {product.id.split('-')[0]}
          </div>
        </div>
        {onView ? (
          <button
            onClick={() => onView(product.id)}
            className="text-left py-2 text-sm font-semibold text-text hover:text-violet-300 transition-colors"
          >
            {product.name} <ArrowRight className="w-3.5 h-3.5 ml-1 text-text-dim opacity-0 group-hover:opacity-100 transition-opacity" />
          </button>
        ) : (
          <h3 className="text-sm font-semibold text-text">{product.name}</h3>
        )}
        <p className="text-xs text-text-muted line-clamp-2">{product.description}</p>
        <div className="mt-auto flex items-center justify-between gap-2">
          <span className="text-sm font-semibold text-text">{formatMoney(product.price)}</span>
          <Badge
            variant={product.stock === 0 ? 'destructive' : product.stock < 10 ? 'warning' : 'success'}
          >
            {stockIcon(product.stock)}
            {product.stock === 0 ? 'Out of stock' : product.stock < 10 ? 'Low stock' : 'In stock'}
          </Badge>
        </div>
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onAdd(product)}
        disabled={disabled || product.stock === 0}
        className="w-full text-xs mt-3"
      >
        {disabled ? 'Sending…' : product.stock === 0 ? 'Out of stock' : 'Add 1 to cart'}
      </Button>
    </article>
  )
}