import { useEffect, useRef, useState } from 'react'

interface AnimatedNumberProps {
  value: number
  format?: (n: number) => string
}

export function AnimatedNumber({
  value,
  format = (n) => n.toFixed(2),
}: AnimatedNumberProps) {
  const display = useRef(value)
  const [shown, setShown] = useState(value)

  useEffect(() => {
    if (value === display.current) return
    const start = display.current
    const startTime = performance.now()
    let rafId: number
    const loop = (t: number) => {
      const p = Math.min((t - startTime) / 600, 1)
      const eased = 1 - Math.pow(1 - p, 3)
      display.current = start + (value - start) * eased
      setShown(display.current)
      if (p < 1) rafId = requestAnimationFrame(loop)
    }
    rafId = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(rafId)
  }, [value])

  return <span className="tabular-nums">{format(shown)}</span>
}