import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'violet' | 'cyan' | 'ghost' | 'outline' | 'danger'
  size?: 'sm' | 'md' | 'lg'
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'violet', size = 'md', disabled, children, ...props }, ref) => {
    const base =
      'btn-face text-sm font-medium rounded-md transition-colors disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet/50'
    const variants = {
      violet:
        'bg-violet-600 text-white shadow-[0_0_0_1px_rgba(124,58,237,0.35)] hover:bg-violet-500 focus-visible:ring-violet/60',
      cyan:
        'bg-cyan-500 text-ink shadow-[0_0_0_1px_rgba(34,211,238,0.35)] hover:bg-cyan-400 focus-visible:ring-cyan/60',
      ghost:
        'bg-transparent text-text-muted border border-transparent hover:bg-surface-lift focus-visible:ring-violet/40',
      outline:
        'border border-border text-text hover:bg-surface-lift focus-visible:ring-violet/40',
      danger:
        'bg-red-900/25 text-red-400 border border-red-900/35 hover:bg-red-900/40 focus-visible:ring-red-500/30',
    }
    const sizes = {
      sm: 'px-3 py-1.5 text-xs',
      md: 'px-5 py-2.5',
      lg: 'px-8 py-3 text-base',
    }
    return (
      <div className="btn-surface inline-block">
        <button
          ref={ref}
          className={cn(base, variants[variant], sizes[size], className)}
          disabled={disabled}
          {...props}
        >
          {children}
        </button>
      </div>
    )
  },
)
Button.displayName = 'Button'