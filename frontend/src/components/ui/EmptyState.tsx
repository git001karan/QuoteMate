import type { ReactNode } from 'react'

interface EmptyStateProps {
  title: string
  description: string
  icon?: ReactNode
  action?: ReactNode
}

export function EmptyState({
  title,
  description,
  icon,
  action,
}: EmptyStateProps) {
  return (
    <section className="flex flex-col items-center justify-center text-center">
      {icon && (
        <div className="w-16 h-16 rounded-2xl border border-border flex items-center justify-center mb-4 text-text-dim">
          {icon}
        </div>
      )}
      <h3 className="text-sm font-semibold text-text mb-2">{title}</h3>
      <p className="text-xs text-text-muted max-w-xs mb-6">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </section>
  )
}