import { AlertCircle, CheckCircle, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useToast } from '@/hooks/useToast'
import { cn } from '@/lib/utils'

export function ToastList() {
  const { toasts, dismiss } = useToast()
  return (
    <div className="fixed top-6 right-6 z-50 flex flex-col gap-2 pointer-events-none">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10, transition: { duration: 0.2 } }}
            className="pointer-events-auto"
          >
            <div
              className={cn(
                'flex items-start gap-3 rounded-xl border p-4 shadow-premium min-w-[320px]',
                t.variant === 'destructive'
                  ? 'bg-red-900/45 border-red-900/50 text-red-100'
                  : t.variant === 'success'
                    ? 'bg-emerald-900/35 border-emerald-900/40 text-emerald-100'
                    : 'bg-surface border-border text-text',
              )}
            >
              {t.variant === 'destructive' ? (
                <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
              ) : t.variant === 'success' ? (
                <CheckCircle className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
              ) : null}
              <div className="flex-1">
                <h4 className="text-sm font-semibold leading-tight">{t.title}</h4>
                {t.description && (
                  <p className="text-xs text-text-muted mt-1 leading-relaxed">
                    {t.description}
                  </p>
                )}
              </div>
              <button
                onClick={() => dismiss(t.id)}
                className="text-text-dim hover:text-text transition-colors p-1 rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}