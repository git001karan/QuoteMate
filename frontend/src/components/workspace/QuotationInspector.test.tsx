import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QuotationInspector } from './QuotationInspector'
import type { QuotationBreakdown, CartContents } from '@/types'

const emptyQuotation: QuotationBreakdown = {
  quotation_id: null,
  sender_id: 'customer_001',
  status: 'INVALID',
  items: [],
  subtotal: 0,
  tax_rate: 0,
  tax_amount: 0,
  total: 0,
  enquiry_id: null,
  stock_issues: [],
  is_valid: false,
}

const emptyCart: CartContents = {
  sender_id: 'customer_001',
  items: [],
  subtotal: 0,
  is_empty: true,
}

const draftQuotation: QuotationBreakdown = {
  quotation_id: 'Q-001',
  sender_id: 'customer_001',
  status: 'DRAFT',
  items: [
    {
      product_id: 'p1',
      name: 'Mechanical Keyboard',
      quantity: 2,
      unit_price: 5000,
      line_total: 10000,
    },
  ],
  subtotal: 10000,
  tax_rate: 18,
  tax_amount: 1800,
  total: 11800,
  enquiry_id: null,
  stock_issues: [],
  is_valid: true,
}

const confirmedQuotation: QuotationBreakdown = {
  ...draftQuotation,
  status: 'CONFIRMED',
  enquiry_id: 'ENQ-20260101-ABCD',
}

const cartWithItems: CartContents = {
  sender_id: 'customer_001',
  items: [
    {
      product_id: 'p1',
      name: 'Mechanical Keyboard',
      unit_price: 5000,
      quantity: 2,
      line_total: 10000,
    },
  ],
  subtotal: 10000,
  is_empty: false,
}

describe('QuotationInspector', () => {
  it('shows empty state when no quotation', () => {
    render(
      <QuotationInspector
        quotation={emptyQuotation}
        cart={emptyCart}
        conversationState={null}
        onConfirm={vi.fn()}
        onDecline={vi.fn()}
        onClearCart={vi.fn()}
      />,
    )
    expect(screen.getByText('No draft quotation')).toBeInTheDocument()
  })

  it('renders quotation details for a draft', () => {
    render(
      <QuotationInspector
        quotation={draftQuotation}
        cart={emptyCart}
        conversationState={null}
        onConfirm={vi.fn()}
        onDecline={vi.fn()}
        onClearCart={vi.fn()}
      />,
    )
    expect(screen.getByText('Quotation')).toBeInTheDocument()
    expect(screen.getByText('₹11800.00')).toBeInTheDocument()
    expect(screen.getByText('DRAFT')).toBeInTheDocument()
  })

  it('shows confirm and decline buttons when awaiting confirmation', () => {
    render(
      <QuotationInspector
        quotation={draftQuotation}
        cart={emptyCart}
        conversationState='AWAITING_CONFIRMATION'
        onConfirm={vi.fn()}
        onDecline={vi.fn()}
        onClearCart={vi.fn()}
      />,
    )
    expect(screen.getByText('Confirm quotation')).toBeInTheDocument()
    expect(screen.getByText('Decline')).toBeInTheDocument()
  })

  it('shows enquiry ID when confirmed', () => {
    render(
      <QuotationInspector
        quotation={confirmedQuotation}
        cart={emptyCart}
        conversationState='CONFIRMED'
        onConfirm={vi.fn()}
        onDecline={vi.fn()}
        onClearCart={vi.fn()}
      />,
    )
    expect(screen.getByText('ENQ-20260101-ABCD')).toBeInTheDocument()
    expect(screen.getByText('Confirmed — enquiry created')).toBeInTheDocument()
  })

  it('copies enquiry ID to clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })

    render(
      <QuotationInspector
        quotation={confirmedQuotation}
        cart={emptyCart}
        conversationState='CONFIRMED'
        onConfirm={vi.fn()}
        onDecline={vi.fn()}
        onClearCart={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByText('Copy'))
    expect(writeText).toHaveBeenCalledWith('ENQ-20260101-ABCD')
  })

  it('shows clear cart button when cart has items', () => {
    render(
      <QuotationInspector
        quotation={draftQuotation}
        cart={cartWithItems}
        conversationState={null}
        onConfirm={vi.fn()}
        onDecline={vi.fn()}
        onClearCart={vi.fn()}
      />,
    )
    expect(screen.getByText(/Clear cart/)).toBeInTheDocument()
  })

  it('does not show clear cart button when cart is empty', () => {
    render(
      <QuotationInspector
        quotation={emptyQuotation}
        cart={emptyCart}
        conversationState={null}
        onConfirm={vi.fn()}
        onDecline={vi.fn()}
        onClearCart={vi.fn()}
      />,
    )
    expect(screen.queryByText(/Clear cart/)).not.toBeInTheDocument()
  })
})