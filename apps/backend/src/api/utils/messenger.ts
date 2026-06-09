const graphVersion = () => process.env.FB_GRAPH_VERSION || "v20.0"

type MessengerProduct = {
  title?: string
  url?: string
  image?: string
  price_from?: string
  discount?: string
}

export const sendMessengerMessage = async (psid: string, text: string, payload?: unknown) => {
  const elements = genericTemplateElements(payload)
  const textToSend = messengerPlainText(text, Boolean(elements.length))
  const sent: Array<Awaited<ReturnType<typeof sendMessengerPayload>>> = []

  if (textToSend) {
    sent.push(await sendMessengerPayload(psid, { text: textToSend }))
  }
  for (let index = 0; index < elements.length; index += 10) {
    sent.push(await sendMessengerPayload(psid, {
      attachment: {
        type: "template",
        payload: {
          template_type: "generic",
          elements: elements.slice(index, index + 10),
        },
      },
    }))
  }

  return sent[sent.length - 1] || { ok: false, skipped: true, reason: "empty_message" }
}

const sendMessengerPayload = async (psid: string, message: Record<string, unknown>) => {
  const token = process.env.FB_PAGE_ACCESS_TOKEN
  if (!token) {
    console.info("[MESSENGER_OUTGOING_SKIPPED]", {
      reason: "missing_FB_PAGE_ACCESS_TOKEN",
      psid,
    })
    return { ok: false, skipped: true, reason: "missing_FB_PAGE_ACCESS_TOKEN" }
  }

  const response = await fetch(`https://graph.facebook.com/${graphVersion()}/me/messages?access_token=${encodeURIComponent(token)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      recipient: { id: psid },
      message,
    }),
  })

  const body = await response.json().catch(() => null)
  console.info("[MESSENGER_OUTGOING]", {
    psid,
    status: response.status,
    ok: response.ok,
  })
  return { ok: response.ok, status: response.status, response: body }
}

const genericTemplateElements = (payload: unknown) => {
  if (!payload || typeof payload !== "object") return []
  const data = payload as Record<string, unknown>
  const product = data.product && typeof data.product === "object" ? data.product as MessengerProduct : null
  const rawProducts = Array.isArray(data.products) ? data.products : product ? [product] : []

  return rawProducts
    .filter((item): item is MessengerProduct => Boolean(item && typeof item === "object"))
    .map((product) => {
      const url = typeof product.url === "string" && product.url.startsWith("https://") ? product.url : null
      const image = typeof product.image === "string" && product.image.startsWith("https://") ? product.image : null
      const subtitle = [
        product.price_from ? `Giá từ ${product.price_from}` : null,
        product.discount ? `Ưu đãi: ${product.discount}` : null,
      ].filter(Boolean).join("\n").slice(0, 80) || "Xem thông tin sản phẩm"

      return {
        title: String(product.title || "Sản phẩm").slice(0, 80),
        subtitle,
        ...(image ? { image_url: image } : {}),
        ...(url ? {
          default_action: {
            type: "web_url",
            url,
            webview_height_ratio: "tall",
          },
          buttons: [{
            type: "web_url",
            url,
            title: "Xem chi tiết",
            webview_height_ratio: "tall",
          }],
        } : {}),
      }
    })
}

const messengerPlainText = (text: string, hasTemplate: boolean) => {
  const stripped = text
    .replace(/!\[[^\]]*]\([^)]+\)/g, "")
    .replace(/\[([^\]]+)]\([^)]+\)/g, "$1")
    .replace(/###/g, "")
    .replace(/\*\*/g, "")
    .replace(/\*   /g, "- ")

  const lines = stripped
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !hasTemplate || !line.startsWith("- "))

  return lines.join("\n").slice(0, 1900)
}
