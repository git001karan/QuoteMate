import { useEffect, useRef } from 'react'
import { AnimatePresence, useReducedMotion } from 'framer-motion'
import { MessageBubble } from './MessageBubble'
import type { Message } from '@/hooks/useConversation'

interface ConversationTimelineProps {
  messages: Message[]
  onRetry: (messageId: string) => void
}

export function ConversationTimeline({
  messages,
  onRetry,
}: ConversationTimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const reducedMotion = useReducedMotion() ?? false

  // Honest scroll behavior: new messages scroll the timeline into view.
  // No claim is made about recovering history the API cannot provide.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: reducedMotion ? 'auto' : 'smooth' })
  }, [messages, reducedMotion])

  return (
    <div
      ref={containerRef}
      className="flex flex-col h-full gap-0"
      aria-label="Conversation timeline"
    >
      <AnimatePresence mode="wait">
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            onRetry={onRetry}
            reducedMotion={reducedMotion}
          />
        ))}
      </AnimatePresence>
    </div>
  )
}