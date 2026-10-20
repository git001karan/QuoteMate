import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/apiClient'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'

import type { ConversationSummary } from '@/types'

interface ConversationsViewProps {
  onSelectSender: (senderId: string) => void
}

export function ConversationsView({ onSelectSender }: ConversationsViewProps) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [newSender, setNewSender] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.conversations()
      setConversations(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load conversations')
      setConversations([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleSwitch = useCallback(
    (senderId: string) => {
      onSelectSender(senderId)
    },
    [onSelectSender],
  )

  const handleNewSender = useCallback(() => {
    const id = newSender.trim()
    if (!id) return
    onSelectSender(id)
    setNewSender('')
  }, [newSender, onSelectSender])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-text tracking-tight">
          Customer conversations
        </h2>
        <p className="text-xs text-text-muted">
          All per-sender conversations on the backend
        </p>
      </div>

      <div className="rounded-lg border border-border bg-surface-lift p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-semibold text-text-dim uppercase tracking-wider">
            Switch customer
          </span>
          <InputRow
            value={newSender}
            onChange={(e) => setNewSender(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleNewSender()
            }}
            placeholder="e.g. customer_002"
          />
          <Button variant="violet" size="sm" onClick={handleNewSender}>
            Switch
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-900/30 bg-red-900/10 p-3">
          <p className="text-xs text-red-300">
            Could not load conversations: {error}
          </p>
        </div>
      )}

      <div
        role="list"
        className={loading && conversations.length === 0 ? 'min-h-[200px]' : 'space-y-2'}
        aria-label="Conversations"
      >
        {loading && conversations.length === 0 ? (
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <SkeletonRow key={i} />
            ))}
          </div>
        ) : conversations.length === 0 ? (
          <EmptyState
            title="No conversations yet"
            description="Send a message in the workspace to create a conversation, then return here to switch between customers."
          />
        ) : (
          conversations.map((conv) => (
            <ConversationRow
              key={conv.sender_id}
              conv={conv}
              onSelect={handleSwitch}
            />
          ))
        )}
      </div>
    </div>
  )
}

function InputRow({
  value,
  onChange,
  onKeyDown,
  placeholder,
}: {
  value: string
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  onKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void
  placeholder?: string
}) {
  return (
    <input
      className="flex-1 h-8 rounded-md border border-border bg-surface-lift px-2 py-1 text-sm text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet/50"
      value={value}
      onChange={onChange}
      onKeyDown={onKeyDown}
      placeholder={placeholder}
    />
  )
}

function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 px-3 py-2.5">
      <div className="h-9 w-20 rounded-full bg-surface-lift animate-pulse" />
      <div className="flex-1">
        <div className="h-4 w-2/3 bg-surface-lift animate-pulse" />
        <div className="h-3 w-1/3 mt-1.5 bg-surface-lift animate-pulse" />
      </div>
    </div>
  )
}

function ConversationRow({
  conv,
  onSelect,
}: {
  conv: ConversationSummary
  onSelect: (senderId: string) => void
}) {
  return (
    <button
      onClick={() => onSelect(conv.sender_id)}
      className="w-full flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg border border-transparent bg-transparent hover:bg-surface-lift hover:border-border transition-colors text-left"
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-text truncate">{conv.sender_id}</span>
          <Badge variant="secondary" className="text-[10px]">
            {conv.state}
          </Badge>
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[10px] text-text-muted">
            Updated {new Date(conv.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
          {conv.pending_product_id && (
            <span className="text-[10px] text-violet-300">Waiting on {conv.pending_product_id}</span>
          )}
        </div>
      </div>
      <span className="text-[10px] text-text-dim">Select</span>
    </button>
  )
}