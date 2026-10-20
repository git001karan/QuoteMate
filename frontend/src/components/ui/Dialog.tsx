import { useCallback, useEffect, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { motion } from 'framer-motion'

interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title?: string
  children: ReactNode
}

export function Dialog({ open, onOpenChange, title, children }: DialogProps) {
  const contentRef = useRef<HTMLDivElement>(null)

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') onOpenChange(false)
    },
    [onOpenChange],
  )

  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
      contentRef.current?.focus()
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [open])

  if (!open) return null

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={() => onOpenChange(false)}
        className="fixed inset-0 z-50 bg-ink/70 backdrop-blur-sm"
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 24 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 24 }}
        onClick={(e) => e.stopPropagation()}
        className="fixed left-[50%] top-[50%] z-50 -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl rounded-2xl border border-border bg-surface shadow-premium"
      >
        <div ref={contentRef} tabIndex={-1} onKeyDown={onKeyDown} className="p-6">
          {title && (
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-text">{title}</h3>
              <button
                onClick={() => onOpenChange(false)}
                className="text-text-muted hover:text-text transition-colors p-1 rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          )}
          <div className="space-y-4">{children}</div>
        </div>
      </motion.div>
    </>
  )
}