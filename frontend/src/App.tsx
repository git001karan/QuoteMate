import { useCallback, useEffect, useState } from 'react'
import { ToastList } from '@/components/ui/Toast'
import { ConnectionBanner } from '@/components/ui/ConnectionBanner'
import { Shell } from '@/components/layout/Shell'
import { WorkspaceView } from '@/components/views/WorkspaceView'
import { CatalogueView } from '@/components/views/CatalogueView'
import { ConversationsView } from '@/components/views/ConversationsView'
import { useConnection } from '@/hooks/useConnection'
import { useSender } from '@/hooks/useSender'
import { useConversation } from '@/hooks/useConversation'
import { useToast } from '@/hooks/useToast'
import type { Product } from '@/types'

type View = 'workspace' | 'catalogue' | 'conversations'

function ConversationArea({
  senderId,
  connectionStatus,
  onRetry,
}: {
  senderId: string
  connectionStatus: ReturnType<typeof useConnection>['status']
  onRetry: ReturnType<typeof useConnection>['check']
}) {
  const {
    messages,
    session,
    sending,
    sendError,
    send,
    retry,
    confirmQuotation,
    declineQuotation,
    loadSessionState,
  } = useConversation({ senderId })

  return (
    <WorkspaceView
      senderId={senderId}
      connectionStatus={connectionStatus}
      messages={messages}
      session={session}
      sending={sending}
      sendError={sendError}
      send={send}
      retry={retry}
      confirmQuotation={confirmQuotation}
      declineQuotation={declineQuotation}
      loadSessionState={loadSessionState}
      onRetry={onRetry}
    />
  )
}

export function App() {
  const { status, error, check } = useConnection()
  const { senderId, setSenderId } = useSender()
  const { toast } = useToast()

  const [view, setView] = useState<View>('workspace')
  const [conversationKey, setConversationKey] = useState(senderId)

  // Force a full remount of the conversation area when the sender changes so
  // that useConversation starts with fresh message state for the new sender.
  useEffect(() => {
    setConversationKey(senderId)
  }, [senderId])

  const { send } = useConversation({ senderId })

  const handleAddToCart = useCallback(
    async (product: Product) => {
      try {
        await send(`add ${product.name} to cart`)
        toast({
          title: 'Added to cart',
          description: product.name,
          variant: 'success',
        })
      } catch (err) {
        toast({
          title: 'Failed to add to cart',
          description: err instanceof Error ? err.message : 'Unknown error',
          variant: 'destructive',
        })
      }
    },
    [send, toast],
  )

  const handleSwitchSender = useCallback(
    (newSenderId: string) => {
      setSenderId(newSenderId)
      setView('workspace')
    },
    [setSenderId],
  )

  return (
    <Shell
      view={view}
      onViewChange={setView}
      senderId={senderId}
      connection={{ status, error, check }}
    >
      <ToastList />
      <ConnectionBanner />

      {view === 'workspace' && (
        <ConversationArea
          key={conversationKey}
          senderId={senderId}
          connectionStatus={status}
          onRetry={check}
        />
      )}

      {view === 'catalogue' && (
        <CatalogueView senderId={senderId} onAddToCart={handleAddToCart} />
      )}

      {view === 'conversations' && (
        <ConversationsView onSelectSender={handleSwitchSender} />
      )}
    </Shell>
  )
}