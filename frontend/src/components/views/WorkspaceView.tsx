import { useCallback } from 'react'
import { RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { ConversationTimeline } from '@/components/workspace/ConversationTimeline'
import { MessageComposer } from '@/components/workspace/MessageComposer'
import { QuotationInspector } from '@/components/workspace/QuotationInspector'
import { useConversation } from '@/hooks/useConversation'
import type { ConnectionStatus } from '@/hooks/useConnection'
import { truncate } from '@/lib/utils'

interface WorkspaceViewProps {
  senderId: string
  connectionStatus: ConnectionStatus
  onRetry: () => void
  messages: ReturnType<typeof useConversation>['messages']
  session: ReturnType<typeof useConversation>['session']
  sending: ReturnType<typeof useConversation>['sending']
  sendError: ReturnType<typeof useConversation>['sendError'] | null
  send: ReturnType<typeof useConversation>['send']
  retry: ReturnType<typeof useConversation>['retry']
  confirmQuotation: ReturnType<typeof useConversation>['confirmQuotation']
  declineQuotation: ReturnType<typeof useConversation>['declineQuotation']
  loadSessionState: ReturnType<typeof useConversation>['loadSessionState']
}

export function WorkspaceView({
  senderId,
  connectionStatus,

  messages,
  session,
  sending,
  sendError,
  send,
  retry,
  confirmQuotation,
  declineQuotation,
  loadSessionState,
}: WorkspaceViewProps) {
  const offline = connectionStatus !== 'online'
  const quotation = session.quotation
  const cart = session.cart
  const conversationState = session.conversation?.state ?? null

  const handleClearCart = useCallback(async () => {
    // The backend clears the cart and cancels the draft when it processes a
    // clear-cart request — we route through the real message endpoint so the
    // timeline stays honest.
    await send('clear my cart')
  }, [send])

  return (
    <div className="flex flex-col gap-4 lg:gap-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-text tracking-tight">
            Conversation
          </h2>
          <p className="text-xs text-text-muted">Sender: {truncate(senderId, 24)}</p>
        </div>
        <Badge variant="secondary" className="text-[11px] truncate max-w-xs">
          {truncate(senderId, 20)}
        </Badge>
      </div>

      <div className="flex-1 min-h-0 flex flex-col gap-0 border border-border rounded-xl bg-surface-lift">
        {messages.length === 0 ? (
          <EmptyState
            title="Start a conversation"
            description={
              offline
                ? 'Backend unavailable — retry the connection, then send your first message.'
                : 'Ask about products, prices, or request a quotation. Every message is sent to the backend with a unique event id.'
            }
            icon={offline ? <span className="w-6 h-6 text-red-400" /> : null}
          />
        ) : (
          <ConversationTimeline messages={messages} onRetry={retry} />
        )}
      </div>

      <MessageComposer
        onSend={send}
        sending={sending}
        disabled={offline}
        error={sendError}
        placeholder={
          offline
            ? 'Backend disconnected — retry to enable messaging…'
            : 'Ask about products, prices, or request a quotation…'
        }
      />

      <div className="flex items-center gap-2 px-3 py-1.5 text-xs">
        <span className="w-1.5 h-1.5 rounded-full">
          {offline ? (
            <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
          ) : (
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          )}
        </span>
        <span className="text-text-muted">
          {offline ? 'Backend disconnected' : 'Backend online'}
        </span>
        {!offline && (
          <button
            onClick={loadSessionState}
            className="ml-auto text-text-muted underline underline-offset-2 hover:text-text transition-colors"
            title="Restore cart and quotation state from the backend"
          >
            <RefreshCw className="w-3 h-3 inline mr-1" /> Refresh state
          </button>
        )}
      </div>

      <QuotationInspector
        quotation={quotation}
        cart={cart}
        conversationState={conversationState}
        onConfirm={confirmQuotation}
        onDecline={declineQuotation}
        onClearCart={handleClearCart}
      />
    </div>
  )
}