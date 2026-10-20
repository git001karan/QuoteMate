import type {
  CartContents,
  ConversationSummary,
  HandoffSummary,
  IncomingMessage,
  ProcessedMessageReply,
  Product,
} from '@/types'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

const BASE = ((import.meta as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')

async function json<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const res = await fetch(input, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    let detail: unknown
    try {
      detail = await res.json()
    } catch {
      detail = res.statusText
    }
    const msg =
      typeof detail === 'object' && detail !== null && 'detail' in detail
        ? String((detail as { detail: unknown }).detail)
        : `HTTP ${res.status}`
    throw new ApiError(res.status, msg, detail)
  }
  if (res.status === 204) return null as unknown as T
  return res.json()
}

export const api = {
  health: () =>
    json<{
      status: string
      timestamp: string
      service: string
      version: string
    }>(`${BASE}/health`),
  products: () => json<Product[]>(`${BASE}/products`),
  product: (id: string) =>
    json<Product>(`${BASE}/products/${encodeURIComponent(id)}`),
  sendMessage: (payload: IncomingMessage) =>
    json<ProcessedMessageReply>(`${BASE}/messages`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  cart: (senderId: string) =>
    json<CartContents>(`${BASE}/cart/${encodeURIComponent(senderId)}`),
  clearCart: (senderId: string) =>
    json<{ message: string; sender_id: string }>(
      `${BASE}/cart/${encodeURIComponent(senderId)}`,
      { method: 'DELETE' },
    ),
  conversations: () => json<ConversationSummary[]>(`${BASE}/conversations`),
  conversation: (senderId: string) =>
    json<ConversationSummary>(
      `${BASE}/conversations/${encodeURIComponent(senderId)}`,
    ),
  handoffs: (senderId: string) =>
    json<HandoffSummary[]>(`${BASE}/handoffs/${encodeURIComponent(senderId)}`),
}

export { BASE }

