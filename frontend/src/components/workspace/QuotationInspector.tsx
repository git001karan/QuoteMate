import { useCallback, useState } from 'react'
import { Copy, CheckCircle2, AlertTriangle, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { AnimatedNumber } from './AnimatedNumber'
import { formatMoney, truncate } from '@/lib/utils'
import type { QuotationBreakdown, CartContents } from '@/types'

interface QuotationInspectorProps {
  quotation: QuotationBreakdown | null
  cart: CartContents | null
  conversationState: string | null
  onConfirm: () => void
  onDecline: () => void
  onClearCart: () => void
}

export function QuotationInspector({
  quotation,
  cart,
  conversationState,
  onConfirm,
  onDecline,
  onClearCart,
}: QuotationInspectorProps) {
  const [copyConfirm, setCopyConfirm] = useState(false)
  const [clearing, setClearing] = useState(false)

  const showEmpty = !quotation || quotation.items.length === 0

  const statusLabel = quotation?.status
  const awaitingConfirmation =
    conversationState === 'AWAITING_CONFIRMATION' &&
    (quotation?.items?.length ?? 0) > 0

  const handleCopyEnquiry = useCallback(() => {
    if (!quotation?.enquiry_id) return
    navigator.clipboard.writeText(quotation.enquiry_id).then(() => {
      setCopyConfirm(true)
      setTimeout(() => setCopyConfirm(false), 1600)
    })
  }, [quotation?.enquiry_id])

  const handleClearCart = useCallback(async () => {
    setClearing(true)
    try {
      await onClearCart()
    } finally {
      setClearing(false)
    }
  }, [onClearCart])

  const stockIssues = quotation?.stock_issues || []
  const hasStockIssues = stockIssues.length > 0

  if (showEmpty) {
    return (
      <section className="panel p-6">
        <div className="flex flex-col items-center justify-center h-64 text-center">
          <div className="w-12 h-12 rounded-2xl border border-border flex items-center justify-center mb-3 text-text-dim">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <h3 className="text-sm font-semibold text-text mb-1">No draft quotation</h3>
          <p className="text-xs text-text-muted max-w-xs">
            Ask for a quote in the workspace — for example “2 mechanical
            keyboards and 1 mouse” — and a draft appears here for review.
          </p>
        </div>
      </section>
    )
  }

  return (
    <section className="panel p-6 flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text tracking-tight">
            Quotation
          </h3>
          <p className="text-xs text-text-muted">
            {truncate(quotation.quotation_id ?? '', 28)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge
            variant={
              statusLabel === 'CONFIRMED'
                ? 'success'
                : statusLabel === 'CANCELLED'
                  ? 'destructive'
                  : statusLabel === 'INVALID'
                    ? 'warning'
                    : 'default'
            }
          >
            {statusLabel}
          </Badge>
        </div>
      </div>

      {/* Stock issues from the backend — never fabricated */}
      {hasStockIssues && (
        <div className="rounded-xl border border-amber-900/30 bg-amber-900/10 p-3">
          <div className="flex items-start gap-2 text-xs">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-amber-200 leading-tight">
                Stock issue{stockIssues.length > 1 ? 's' : ''}
              </p>
              <ul className="mt-1 text-amber-300/80 list-disc list-inside space-y-1">
                {stockIssues.map((issue, i) => (
                  <li key={i}>
                    {truncate(issue.name, 24)} ({issue.product_id}):{' '}
                    {issue.reason === 'unknown'
                      ? 'not in catalogue'
                      : issue.reason === 'unavailable'
                        ? 'out of stock'
                        : `insufficient stock (requested ${issue.requested_quantity}, available ${issue.available_quantity})`}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Line items */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-left text-[10px] font-semibold text-text-dim uppercase tracking-wider border-b border-border pb-2">
              <th className="pr-3">Product</th>
              <th className="w-16 text-right">Qty</th>
              <th className="w-24 text-right">Unit</th>
              <th className="w-24 text-right">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {quotation.items.map((item) => (
              <tr key={item.product_id} className="text-text align-middle">
                <td className="py-3 pr-3">
                  <p className="font-medium">{truncate(item.name, 22)}</p>
                  <p className="text-[10px] text-text-muted">{item.product_id}</p>
                </td>
                <td className="py-3 text-right">{item.quantity}</td>
                <td className="py-3 text-right">{formatMoney(item.unit_price)}</td>
                <td className="py-3 text-right font-medium">{formatMoney(item.line_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/* Totals */}
      <div className="border-t border-border pt-3">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-text-muted">Subtotal</span>
          <span className="tabular-nums text-text">{formatMoney(quotation.subtotal)}</span>
        </div>
        <div className="flex justify-between text-sm mb-1">
          <span className="text-text-muted">Tax (18%)</span>
          <span className="tabular-nums text-text">{formatMoney(quotation.tax_amount)}</span>
        </div>
        <div className="flex justify-between mt-1.5">
          <span className="text-sm font-semibold text-text">Total</span>
          <span className="text-sm font-semibold text-violet-200 tabular-nums">
            <AnimatedNumber
              value={quotation.total}
              format={(n) => `₹${n.toFixed(2)}`}
            />
          </span>
        </div>
      </div>

      {/* Enquiry ID — only when the backend assigned one after confirmation */}
      {quotation.enquiry_id && (
        <div className="rounded-xl border border-violet/20 bg-violet/5 p-3">
          <div className="flex items-start gap-2">
            <div className="w-6 h-6 rounded-lg bg-violet/20 flex items-center justify-center text-violet-200 text-xs shrink-0">
              <Copy className="w-3 h-3" />
            </div>
            <div className="flex-1">
              <p className="text-[10px] font-semibold text-violet-200 uppercase tracking-wider mb-0.5">
                Enquiry ID
              </p>
              <div className="flex items-center gap-2">
                <code className="text-xs font-mono text-text break-all">
                  {quotation.enquiry_id}
                </code>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCopyEnquiry}
                  className="h-6 px-2 text-xs"
                >
                  {copyConfirm ? 'Copied' : 'Copy'}
                </Button>
              </div>
              <p className="text-[10px] text-violet-200/70 mt-1">
                Assigned by the backend after confirmation — the sales team will
                follow up on this reference.
              </p>
            </div>
          </div>
        </div>
      )}

      {statusLabel === 'CONFIRMED' && (
        <p className="text-[10px] text-emerald-400 flex items-center gap-1.5">
          <CheckCircle2 className="w-3 h-3" /> Confirmed — enquiry created
        </p>
      )}

      {/* Confirmation / decline actions */}
      {awaitingConfirmation && !hasStockIssues && (
        <div className="grid grid-cols-2 gap-2">
          <Button
            variant="violet"
            onClick={onConfirm}
            className="shadow-[0_0_24px_rgba(124,58,237,0.35)]"
          >
            Confirm quotation
          </Button>
          <Button variant="danger" onClick={onDecline}>
            Decline
          </Button>
        </div>
      )}

      {awaitingConfirmation && hasStockIssues && (
        <p className="text-xs text-amber-300">
          Resolve the stock issues above, then confirm. Adjust quantities in the
          workspace and send again.
        </p>
      )}

      {statusLabel === 'DECLINED' && (
        <p className="text-[10px] text-red-400 flex items-center gap-1.5">
          <AlertTriangle className="w-3 h-3" /> Declined — draft cancelled
        </p>
      )}

      {statusLabel === 'INVALID' && (
        <p className="text-xs text-text-muted">
          No valid quotation yet. Add items from the catalogue and request a
          quote in the workspace.
        </p>
      )}

      {cart && !cart.is_empty && !clearing && (
        <button
          onClick={handleClearCart}
          className="mt-3 w-full flex items-center justify-center gap-2 text-xs text-text-muted underline underline-offset-4 hover:text-text transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" /> Clear cart &amp; cancel draft
        </button>
      )}
    </section>
  )
}