import { RefreshCw } from 'lucide-react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { formatRelativeTime } from '@/lib/utils'
import type { Message } from '@/hooks/useConversation'

interface MessageBubbleProps {
  message: Message
  onRetry: (messageId: string) => void
  reducedMotion: boolean
}

export function MessageBubble({
  message,
  onRetry,
  reducedMotion,
}: MessageBubbleProps) {
  const isCustomer = message.role === 'customer'
  const showStatus = isCustomer && message.status !== 'sent'

  const statusContent = (
    <div className="flex items-center gap-2 text-[10px]">
      {message.status === 'sending' ? (
        <span className="flex items-center gap-1 text-violet-300 animate-pulse">
          <RefreshCw className="w-3 h-3" /> sending
        </span>
      ) : message.status === 'error' ? (
        <span className="flex items-center gap-1 text-red-400">
          <span className="w-3 h-3 rounded-full bg-red-900/40 border border-red-500/40" />
          failed
        </span>
      ) : null}
    </div>
  )

  const bubbleClass = isCustomer
    ? 'bg-violet/10 border border-violet/20 text-violet-100'
    : 'bg-surface-lift border border-border text-text'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      transition={reducedMotion ? { duration: 0 } : undefined}
      className="flex w-full mb-6"
      style={{ alignSelf: isCustomer ? 'flex-end' : 'flex-start' }}
    >
      <div
        className={cn(
          'max-w-[82%] w-fit rounded-2xl p-3.5 text-sm leading-relaxed',
          bubbleClass,
        )}
      >
        {message.role === 'assistant' && (
          <p className="text-[10px] text-text-dim mb-1 uppercase tracking-wider font-semibold">
            QuoteMate assistant
          </p>
        )}
        <p className="whitespace-pre-wrap">{message.text}</p>
        {showStatus && (
          <div className="mt-2 flex items-center justify-end gap-2">
            {message.status === 'error' ? (
              <>
                <span className="text-[10px] text-red-400">Send failed</span>
                <button
                  onClick={() => onRetry(message.messageId)}
                  className="text-[10px] underline underline-offset-2 text-violet-300 hover:text-violet-200"
                >
                  Retry
                </button>
              </>
            ) : (
              statusContent
            )}
          </div>
        )}
        {!isCustomer || message.status !== 'error' ? (
          <div className="mt-1 flex justify-end">
            <span className="text-[10px] text-text-dim">{formatRelativeTime(message.timestamp)}</span>
          </div>
        ) : null}
      </div>
    </motion.div>
  )
}