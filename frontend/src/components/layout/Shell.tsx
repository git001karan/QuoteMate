import { useCallback, useState, type ReactNode } from 'react'

import { cn } from '@/lib/utils'
import { Sidebar } from '@/components/layout/Sidebar'
import { TopBar } from '@/components/layout/TopBar'
import type { ConnectionStatus } from '@/hooks/useConnection'

interface ShellProps {
  children: ReactNode
  view: 'workspace' | 'catalogue' | 'conversations'
  onViewChange: (v: 'workspace' | 'catalogue' | 'conversations') => void
  senderId: string
  connection: {
    status: ConnectionStatus
    error: string | null
    check: () => void
  }
}

export function Shell({
  children,
  view,
  onViewChange,
  senderId,
  connection,
}: ShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false)

  const toggleDrawer = useCallback(() => setDrawerOpen((prev) => !prev), [])
  const closeDrawer = useCallback(() => setDrawerOpen(false), [])

  return (
    <div className="relative z-0 min-h-screen selection:bg-violet/30 selection:text-text">
      <aside
        className={cn(
          'fixed left-0 top-0 h-full w-64 border-r border-border z-30 transition-transform duration-300 ease-in-out lg:relative lg:translate-x-0 lg:block',
          drawerOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <Sidebar
          view={view}
          onViewChange={onViewChange}
          senderId={senderId}
          connection={connection}
          drawerOpen={drawerOpen}
          onClose={closeDrawer}
        />
      </aside>
      {drawerOpen && !window.matchMedia('(min-width: 1024px)').matches && (
        <div
          onClick={closeDrawer}
          className="fixed inset-0 z-20 bg-ink/60 backdrop-blur-lg lg:hidden"
          aria-hidden="true"
        />
      )}
      <div className="lg:pl-64 min-h-screen">
        <TopBar onMenu={toggleDrawer} senderId={senderId} />
        <main
          className="relative z-10 max-w-[1600px] mx-auto w-full px-4 py-6 lg:px-8 lg:py-10"
        >
          {children}
        </main>
      </div>
    </div>
  )
}