import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/apiClient'
import { CONFIRM_TEXT, DECLINE_TEXT } from '@/lib/config'
import { generateMessageId } from '@/lib/utils'
import type {
  CartContents,
  ConversationSummary,
  ProcessedMessageReply,
  SessionState,
} from '@/types'

export interface Message {
  id: string
  messageId: string
  senderId: string
  text: string
  role: 'customer' | 'assistant'
  status: 'sending' | 'sent' | 'error'
  timestamp: string
  reply?: ProcessedMessageReply
}

interface UseConversationProps {
  senderId: string
}

export function useConversation({ senderId }: UseConversationProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [session, setSession] = useState<SessionState>({
    cart: null,
    quotation: null,
    conversation: null,
  })
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const inFlightRef = useRef<string | null>(null)

  const applyReply = useCallback((reply: ProcessedMessageReply) => {
    setSession((prev) => ({
      cart: reply.cart ?? prev.cart,
      quotation: reply.quotation ?? prev.quotation,
      conversation:
        reply.conversation_state && prev.conversation
          ? { ...prev.conversation, state: reply.conversation_state }
          : prev.conversation,
    }))
  }, [])

  const loadSessionState = useCallback(async () => {
    try {
      const [cart, conversation] = await Promise.all([
        api.cart(senderId).catch(() => null as CartContents | null),
        api.conversation(senderId).catch(() => null as ConversationSummary | null),
      ])
      setSession((prev) => ({
        ...prev,
        cart: cart ?? prev.cart,
        conversation: conversation ?? prev.conversation,
      }))
    } catch {
      // Best-effort restoration only: the API exposes no message history, so
      // cart and conversation state are restored from the server while the
      // visible timeline starts fresh. No backend persistence is claimed here.
    }
  }, [senderId])

  useEffect(() => {
    loadSessionState()
  }, [senderId, loadSessionState])

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || sending || inFlightRef.current) return

      const messageId = generateMessageId()
      inFlightRef.current = messageId
      setSendError(null)

      const optimistic: Message = {
        id: crypto.randomUUID(),
        messageId,
        senderId,
        text: text.trim(),
        role: 'customer',
        status: 'sending',
        timestamp: new Date().toISOString(),
      }

      setMessages((prev) => [...prev, optimistic])
      setSending(true)

      try {
        const reply = await api.sendMessage({
          message_id: messageId,
          sender_id: senderId,
          text: text.trim(),
          timestamp: optimistic.timestamp,
        })

        setMessages((prev) =>
          prev.map((m) => (m.messageId === messageId ? { ...m, status: 'sent' } : m)),
        )

        // A duplicated reply means the backend already processed this exact
        // event idempotently — do not append a second assistant bubble.
        if (!reply.duplicated) {
          const assistant: Message = {
            id: crypto.randomUUID(),
            messageId: reply.message_id,
            senderId: reply.sender_id,
            text: reply.reply_text,
            role: 'assistant',
            status: 'sent',
            timestamp: new Date().toISOString(),
            reply,
          }
          setMessages((prev) => [...prev, assistant])
        } else {
          setMessages((prev) =>
            prev.map((m) =>
              m.messageId === messageId
                ? { ...m, status: 'sent' }
                : m,
            ),
          )
        }

        applyReply(reply)

        if (reply.is_unsupported) {
          throw new Error(reply.reply_text || 'This request is not supported.')
        }
      } catch (err) {
        setMessages((prev) =>
          prev.map((m) => (m.messageId === messageId ? { ...m, status: 'error' } : m)),
        )
        setSendError(err instanceof Error ? err.message : 'Failed to send message')
        throw err
      } finally {
        setSending(false)
        inFlightRef.current = null
      }
    },
    [senderId, sending, applyReply],
  )

  // Deliberate retry of a failed event preserves the same message id so the
  // backend's duplicate-protection replays the earlier outcome instead of
  // creating a duplicate action.
  const retry = useCallback(
    async (messageId: string) => {
      const msg = messages.find(
        (m) => m.messageId === messageId && m.status === 'error',
      )
      if (!msg) return
      return send(msg.text)
    },
    [messages, send],
  )

  const confirmQuotation = useCallback(async () => send(CONFIRM_TEXT), [send])
  const declineQuotation = useCallback(async () => send(DECLINE_TEXT), [send])

  return {
    messages,
    session,
    sending,
    sendError,
    send,
    retry,
    confirmQuotation,
    declineQuotation,
    loadSessionState,
  }
}