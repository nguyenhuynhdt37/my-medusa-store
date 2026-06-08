import { useCallback, useEffect, useRef, useState } from "react"

const PERMISSION_STORAGE_KEY = "medusan_admin_chat_notification_permission"

export type ChatNotificationMessage = {
  id: string
  senderLabel: string
  content: string
}

const truncate = (value: string, max = 120) => {
  return value.length > max ? `${value.slice(0, max - 1)}...` : value
}

const requestBrowserPermission = async () => {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return "unsupported"
  }

  if (Notification.permission === "default") {
    const permission = await Notification.requestPermission()
    window.localStorage.setItem(PERMISSION_STORAGE_KEY, permission)
    return permission
  }

  window.localStorage.setItem(PERMISSION_STORAGE_KEY, Notification.permission)
  return Notification.permission
}

const playNotificationSound = async () => {
  if (typeof window === "undefined") {
    return
  }

  try {
    const audio = new Audio("/notification.mp3")
    audio.volume = 0.55
    await audio.play()
    return
  } catch (error) {
  }

  try {
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext
    if (!AudioContextClass) {
      return
    }

    const context = new AudioContextClass()
    const oscillator = context.createOscillator()
    const gain = context.createGain()
    oscillator.type = "sine"
    oscillator.frequency.value = 740
    gain.gain.value = 0.035
    oscillator.connect(gain)
    gain.connect(context.destination)
    oscillator.start()
    oscillator.stop(context.currentTime + 0.12)
  } catch (error) {
  }
}

export const useChatNotifications = ({
  baseTitle,
  notificationTitle = "Medusan",
}: {
  baseTitle: string
  notificationTitle?: string
}) => {
  const [unreadCount, setUnreadCount] = useState(0)
  const [permission, setPermission] = useState<string>("default")
  const seenIdsRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    document.title = unreadCount > 0 ? `(${unreadCount}) ${baseTitle}` : baseTitle
  }, [baseTitle, unreadCount])

  useEffect(() => {
    void requestBrowserPermission().then(setPermission)
  }, [])

  const notify = useCallback(
    async (message: ChatNotificationMessage, shouldAlert: boolean) => {
      if (!shouldAlert || seenIdsRef.current.has(message.id)) {
        return
      }

      seenIdsRef.current.add(message.id)
      setUnreadCount((current) => current + 1)

      const body = `${message.senderLabel}: ${truncate(message.content)}`
      if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "granted") {
        new Notification(notificationTitle, {
          body,
          tag: message.id,
        })
      }

      await playNotificationSound()
    },
    [notificationTitle]
  )

  const markRead = useCallback(() => {
    setUnreadCount(0)
  }, [])

  return {
    permission,
    unreadCount,
    notify,
    markRead,
  }
}

