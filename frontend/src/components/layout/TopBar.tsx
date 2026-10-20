import { Menu } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'

interface TopBarProps {
  onMenu: () => void
  senderId: string
}

export function TopBar({ onMenu, senderId }: TopBarProps) {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-border bg-surface/80 backdrop-blur-md -mx-4 px-4 lg:mx-0">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenu}
          className="rounded-lg p-1.5 text-text-muted hover:bg-surface-lift hover:text-text transition-colors lg:hidden"
          aria-label="Open navigation"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold text-text tracking-tight">QuoteMate</span>
          <span className="text-xs text-text-muted">Cerevyn Solutions · PS05</span>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Badge variant="secondary" className="text-[11px] truncate max-w-xs">
          Session: {senderId}
        </Badge>
        <Button variant="ghost" size="sm">
          New message
        </Button>
      </div>
    </header>
  )
}