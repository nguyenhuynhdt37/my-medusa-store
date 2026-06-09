import { useCallback, useEffect, useRef, useState } from "react"

const PERMISSION_STORAGE_KEY = "medusan_admin_chat_notification_permission"

export type ChatNotificationMessage = {
  id: string
  conversationId?: string
  senderLabel: string
  content: string
}

type NotificationSupport = "supported" | "unsupported"

type ServiceWorkerStatus = {
  supported: boolean
  controller: boolean
  registrations: number
  pushSubscription: boolean
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

const getServiceWorkerStatus = async (): Promise<ServiceWorkerStatus> => {
  const unsupported = {
    supported: false,
    controller: false,
    registrations: 0,
    pushSubscription: false,
  }

  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) {
    return unsupported
  }

  const registrations = await navigator.serviceWorker.getRegistrations()
  let pushSubscription = false

  for (const registration of registrations) {
    const subscription = await registration.pushManager?.getSubscription().catch(() => null)
    if (subscription) {
      pushSubscription = true
      break
    }
  }

  const status = {
    supported: true,
    controller: Boolean(navigator.serviceWorker.controller),
    registrations: registrations.length,
    pushSubscription,
  }
  return status
}

const playNotificationSound = async () => {
  if (typeof window === "undefined") {
    return
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
  const [support, setSupport] = useState<NotificationSupport>("supported")
  const [serviceWorkerStatus, setServiceWorkerStatus] = useState<ServiceWorkerStatus | null>(null)
  const seenIdsRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    document.title = unreadCount > 0 ? `(${unreadCount}) ${baseTitle}` : baseTitle
  }, [baseTitle, unreadCount])

  useEffect(() => {
    void requestBrowserPermission().then((nextPermission) => {
      setPermission(nextPermission)
      setSupport(nextPermission === "unsupported" ? "unsupported" : "supported")
    })
    void getServiceWorkerStatus().then(setServiceWorkerStatus)
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
        console.info("[NOTIFICATION_SENT]", {
          conversation_id: message.conversationId || null,
          receiver: "admin",
          title: notificationTitle,
        })
      }

      await playNotificationSound()
    },
    [notificationTitle]
  )

  const testNotification = useCallback(async () => {
    const nextPermission = await requestBrowserPermission()
    setPermission(nextPermission)
    setSupport(nextPermission === "unsupported" ? "unsupported" : "supported")

    if (nextPermission !== "granted" || typeof window === "undefined" || !("Notification" in window)) {
      return false
    }

    new Notification("Medusan Test", {
      body: "Thông báo hoạt động bình thường",
      tag: "medusan-test-notification",
    })
    await playNotificationSound()
    return true
  }, [])

  const markRead = useCallback(() => {
    setUnreadCount(0)
  }, [])

  return {
    permission,
    support,
    serviceWorkerStatus,
    unreadCount,
    notify,
    markRead,
    testNotification,
  }
}
