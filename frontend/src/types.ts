export interface Product {
  id: string
  name: string
  description: string
  price: number
  stock: number
}

export interface CartLineItem {
  product_id: string
  name: string
  unit_price: number
  quantity: number
  line_total: number
}

export interface CartContents {
  sender_id: string
  items: CartLineItem[]
  subtotal: number
  is_empty: boolean
}

export interface QuotationLineBreakdown {
  product_id: string
  name: string
  quantity: number
  unit_price: number
  line_total: number
}

export interface StockIssue {
  product_id: string
  name: string
  requested_quantity: number
  available_quantity: number
  reason: 'unknown' | 'unavailable' | 'insufficient_stock'
}

export interface QuotationBreakdown {
  quotation_id: string | null
  sender_id: string
  status: 'DRAFT' | 'CONFIRMED' | 'CANCELLED' | 'DECLINED' | 'INVALID'
  items: QuotationLineBreakdown[]
  subtotal: number
  tax_rate: number
  tax_amount: number
  total: number
  enquiry_id: string | null
  stock_issues: StockIssue[]
  is_valid: boolean
}

export interface ProcessedMessageReply {
  message_id: string
  sender_id: string
  reply_text: string
  duplicated: boolean
  intent: string | null
  intent_confidence: number | null
  needs_clarification: boolean
  is_unsupported: boolean
  conversation_state: string | null
  cart: CartContents | null
  quotation_id: string | null
  enquiry_id: string | null
  quotation_status: string | null
  quotation: QuotationBreakdown | null
  handoff_id: number | null
  handoff_status: string | null
}

export interface IncomingMessage {
  message_id: string
  sender_id: string
  text: string
  timestamp: string
}

export interface ConversationSummary {
  sender_id: string
  state: string
  pending_product_id: string | null
  created_at: string
  updated_at: string
}

export interface HandoffSummary {
  id: number
  sender_id: string
  message_id: string | null
  reason: string
  status: string
  created_at: string
}

export interface SessionState {
  cart: CartContents | null
  quotation: QuotationBreakdown | null
  conversation: ConversationSummary | null
}