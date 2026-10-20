import { RefreshCw, WifiOff } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { useConnection } from '@/hooks/useConnection'

export function ConnectionBanner() {
  const { status, error, check } = useConnection()
  if (status === 'online') return null
  const connecting = status === 'unknown'

  return (
    <div className="fixed inset-x-0 bottom-4 z-40 flex items-center justify-center pointer-events-none">
      <div className="pointer-events-auto flex w-full max-w-xs flex-col gap-2">
        <div
          className={cn(
            'flex items-center gap-3 rounded-xl border px-3 py-2.5 shadow-premium',
            connecting
              ? 'bg-amber-900/45 border-amber-900/40 text-amber-100'
              : 'bg-red-900/50 border-red-900/45 text-red-100',
          )}
        >
          {connecting ? (
            <div className="relative w-4 h-4 flex-shrink-0">
              <WifiOff className="w-4 h-4 animate-pulse" />
            </div>
          ) : (
            <WifiOff className="w-4 h-4 flex-shrink-0" />
          )}
          <div className="flex-1">
            <p className="text-sm font-semibold leading-tight">
              {connecting ? 'Connecting to backend…' : 'Backend disconnected'}
            </p>
            {error && <p className="text-xs text-red-200/70 mt-1">{error}</p>}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={check}
            disabled={connecting}
          >
            {connecting ? (
              <RefreshCw className="w-3 h-3" />
            ) : (
              'Retry'
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}