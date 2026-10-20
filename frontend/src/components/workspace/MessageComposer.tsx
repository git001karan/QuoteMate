import { useCallback, useRef, useState } from 'react'
import { Send } from 'lucide-react'
import { Button } from '@/components/ui/Button'

interface MessageComposerProps {
  onSend: (text: string) => void
  sending: boolean
  disabled?: boolean
  error?: string | null
  placeholder?: string
}

export function MessageComposer({
  onSend,
  sending,
  disabled = false,
  error,
  placeholder = 'Ask about products, prices, or request a quotation…',
}: MessageComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [value, setValue] = useState('')

  const handleSend = useCallback(() => {
    const text = value.trim()
    if (!text || sending || disabled) return
    onSend(text)
    setValue('')
    textareaRef.current?.focus()
  }, [value, sending, disabled, onSend])

  return (
    <div className="flex w-full flex-col gap-2 border-t border-border bg-surface pt-4">
      {error && (
        <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-red-900/20 border border-red-900/30 text-red-300 text-sm">
          <span className="w-3 h-3 shrink-0 text-red-400" aria-hidden="true">
            !
          </span>
          <span className="leading-relaxed">{error}</span>
        </div>
      )}
      <div className="relative flex gap-2">
        <textarea
          ref={textareaRef}
          className="flex-1 min-h-[48px] rounded-xl border border-border bg-surface-lift px-3 py-2.5 text-sm text-text placeholder:text-text-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet/50 disabled:cursor-not-allowed disabled:opacity-50"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
          placeholder={placeholder}
          disabled={sending || disabled}
          rows={1}
          spellCheck
          autoComplete="off"
        />
        <Button
          variant="violet"
          size="lg"
          disabled={!value.trim() || sending || disabled}
          onClick={handleSend}
        >
          <Send className="w-4 h-4" />
        </Button>
      </div>
      <p className="text-[10px] text-text-dim">
        Shift+Enter for a new line. Every message carries a unique event id.
      </p>
    </div>
  )
}