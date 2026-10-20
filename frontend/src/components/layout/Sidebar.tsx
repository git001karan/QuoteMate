import { useCallback, useState } from 'react'
import { Layout, Package, Clock } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { useSender } from '@/hooks/useSender'
import { cn } from '@/lib/utils'

interface SidebarProps {
  view: 'workspace' | 'catalogue' | 'conversations'
  onViewChange: (v: 'workspace' | 'catalogue' | 'conversations') => void
  senderId: string
  connection: { status: string; error: string | null; check: () => void }
  drawerOpen: boolean
  onClose: () => void
}

const NAV: {
  key: 'workspace' | 'catalogue' | 'conversations'
  label: string
  icon: React.ElementType
}[] = [
  { key: 'workspace', label: 'Workspace', icon: Layout },
  { key: 'catalogue', label: 'Catalogue', icon: Package },
  { key: 'conversations', label: 'Conversations', icon: Clock },
]

export function Sidebar({
  view,
  onViewChange,
  senderId,
  connection,
  drawerOpen,
  onClose,
}: SidebarProps) {
  const { nextSender, setNextSender, confirmNewSender } = useSender()
  const [senderEditing, setSenderEditing] = useState(false)

  const handleNav = useCallback(
    (key: typeof NAV[number]['key']) => {
      onViewChange(key)
      if (!drawerOpen) return
      onClose()
    },
    [onViewChange, drawerOpen, onClose],
  )

  return (
    <div className="flex h-full flex-col border-r border-border bg-surface">
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-border">
        <div className="w-8 h-8 rounded-xl bg-violet/20 flex items-center justify-center shadow-[0_0_24px_rgba(124,58,237,0.30)]">
          <span className="text-white font-bold tracking-tighter">QM</span>
        </div>
        <div className="hidden lg:flex flex-col leading-tight">
          <span className="text-sm font-bold text-text tracking-tight">QuoteMate</span>
          <span className="text-xs text-text-dim uppercase tracking-wider">
            AI quotation workspace
          </span>
        </div>
      </div>

      <nav className="flex-1 px-3 py-3 space-y-0.5">
        {NAV.map((item) => {
          const active = view === item.key
          const Icon = item.icon
          return (
            <button
              key={item.key}
              onClick={() => handleNav(item.key)}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors',
                active
                  ? 'bg-violet/12 text-violet-200 border border-violet/30'
                  : 'text-text-muted hover:bg-surface-lift hover:text-text',
              )}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              <span className="font-medium">{item.label}</span>
            </button>
          )
        })}
      </nav>

      <div className="border-t border-border p-4">
        <div className="flex items-center justify-between px-2 mb-3">
          <span className="text-[10px] font-semibold text-text-dim uppercase tracking-wider">
            Connection
          </span>
          <span className="flex items-center gap-1.5">
            {connection.status === 'online' ? (
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            ) : (
              <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
            )}
            <span className="text-xs font-medium">
              {connection.status === 'online' ? 'Online' : 'Offline'}
            </span>
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={connection.check}
          disabled={connection.status === 'unknown'}
          className="w-full text-xs"
        >
          {connection.status === 'unknown' ? 'Connecting…' : 'Retry backend'}
        </Button>

        <div className="mt-5">
          <div className="flex items-center justify-between px-2 mb-2">
            <span className="text-[10px] font-semibold text-text-dim uppercase tracking-wider">
              Customer
            </span>
            <button
              onClick={() => setSenderEditing(true)}
              className="text-xs text-violet-300 hover:text-violet-200 underline decoration-violet/40 decoration-hover:decoration-violet-200"
              title="Switch customer session"
            >
              Change
            </button>
          </div>
          <div className={senderEditing ? 'flex gap-2' : 'flex items-center gap-2 px-2'}>
            {!senderEditing ? (
              <Badge variant="secondary" className="text-[11px] truncate flex-1">
                {senderId}
              </Badge>
            ) : (
              <>
                <InputInline
                  value={nextSender}
                  onChange={(e) => setNextSender(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') confirmNewSender()
                    if (e.key === 'Escape') setSenderEditing(false)
                  }}
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={confirmNewSender}
                  disabled={!nextSender.trim()}
                >
                  OK
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setSenderEditing(false)}>
                  X
                </Button>
              </>
            )}
          </div>
        </div>

        <div className="mt-5 border-t border-border pt-3 px-2">
          <div className="flex items-center gap-2 px-1 mb-1">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
            <span className="text-[10px] text-text-muted">Milestones 5–7 backend</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function InputInline({
  value,
  onChange,
  onKeyDown,
}: {
  value: string
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  onKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void
}) {
  return (
    <input
      autoFocus
      className="flex-1 h-8 rounded-md border border-border bg-surface-lift px-2 py-1 text-sm text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet/50"
      value={value}
      onChange={onChange}
      onKeyDown={onKeyDown}
    />
  )
}