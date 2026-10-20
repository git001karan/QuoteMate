import { useCallback, useState } from 'react'
import { DEFAULT_SENDER } from '@/lib/config'

export function useSender() {
  const [senderId, setSenderId] = useState(DEFAULT_SENDER)
  const [editing, setEditing] = useState(false)
  const [nextSender, setNextSender] = useState(senderId)

  const startEdit = useCallback(() => {
    setNextSender(senderId)
    setEditing(true)
  }, [senderId])
  const cancelEdit = useCallback(() => setEditing(false), [])
  const confirmNewSender = useCallback(() => {
    if (nextSender.trim()) {
      setSenderId(nextSender.trim())
      setEditing(false)
    }
  }, [nextSender])

  return {
    senderId,
    setSenderId,
    editing,
    setEditing,
    nextSender,
    setNextSender,
    startEdit,
    cancelEdit,
    confirmNewSender,
  }
}