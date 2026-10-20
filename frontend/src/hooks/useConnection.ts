import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/apiClient'

export type ConnectionStatus = 'online' | 'offline' | 'unknown'

export function useConnection(options?: { intervalMs?: number }) {
  const intervalMs = options?.intervalMs ?? 8000
  const [status, setStatus] = useState<ConnectionStatus>('unknown')
  const [lastChecked, setLastChecked] = useState<Date | null>(null)
  const [error, setError] = useState<string | null>(null)

  const check = useCallback(async (): Promise<boolean> => {
    try {
      await api.health()
      setStatus('online')
      setLastChecked(new Date())
      setError(null)
      return true
    } catch (err) {
      setStatus('offline')
      setLastChecked(new Date())
      setError(err instanceof Error ? err.message : 'Backend unreachable')
      return false
    }
  }, [])

  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setTimeout>

    const loop = async () => {
      if (!active) return
      await check()
      if (active) timer = setTimeout(loop, intervalMs)
    }

    // Initial check immediately on mount; keep polling so the UI recovers
    // automatically when the backend comes back online.
    void loop()
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [check, intervalMs])

  return { status, lastChecked, error, check }
}