import { cn } from '@/lib/utils'

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'secondary' | 'success' | 'warning' | 'destructive' | 'outline'
}

export function Badge({
  className,
  variant = 'default',
  ...props
}: BadgeProps) {
  const variants = {
    default: 'bg-violet/10 text-violet-200 border border-violet/20',
    secondary: 'bg-surface-lift text-text-muted border border-border',
    success: 'bg-emerald-900/20 text-emerald-400 border border-emerald-900/30',
    warning: 'bg-amber-900/20 text-amber-400 border border-amber-900/30',
    destructive: 'bg-red-900/20 text-red-400 border border-red-900/30',
    outline: 'bg-transparent border border-border text-text-muted',
  }
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider',
        variants[variant],
        className,
      )}
      {...props}
    />
  )
}