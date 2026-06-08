export type EscalationResult = {
  escalate: boolean
  reason: string
  confidence?: number
}

const keywordGroups: Array<{ reason: string; keywords: string[] }> = [
  {
    reason: "complaint",
    keywords: ["khiếu nại", "khieu nai", "phản ánh", "phan anh", "không hài lòng", "khong hai long", "chất lượng kém", "chat luong kem", "phục vụ tệ", "phuc vu te"],
  },
  {
    reason: "return_request",
    keywords: ["đổi hàng", "doi hang", "trả hàng", "tra hang", "hoàn hàng", "hoan hang"],
  },
  {
    reason: "refund_request",
    keywords: ["hoàn tiền", "hoan tien", "refund", "trả lại tiền", "tra lai tien"],
  },
  {
    reason: "payment_failed",
    keywords: ["thanh toán thất bại", "thanh toan that bai", "bị trừ tiền", "bi tru tien", "không thanh toán được", "khong thanh toan duoc"],
  },
  {
    reason: "abnormal_order",
    keywords: ["giao sai", "giao thiếu", "giao thieu", "đơn hàng mất", "don hang mat", "chưa nhận được hàng", "chua nhan duoc hang"],
  },
  {
    reason: "human_handoff",
    keywords: ["gặp nhân viên", "gap nhan vien", "gặp người thật", "gap nguoi that", "gặp admin", "gap admin", "hỗ trợ trực tiếp", "ho tro truc tiep", "nói chuyện với nhân viên", "noi chuyen voi nhan vien"],
  },
]

const normalize = (value?: string | null) => {
  return (value || "").trim().toLowerCase()
}

export const shouldEscalateToAdmin = ({
  message,
  intent,
  confidence,
  failedResponseCount,
}: {
  message: string
  intent?: string | null
  confidence?: number
  failedResponseCount?: number
}): EscalationResult => {
  const normalizedMessage = normalize(message)
  const normalizedIntent = normalize(intent)

  if (normalizedIntent === "humanhandoffintent" || normalizedIntent.includes("humanhandover") || normalizedIntent.includes("handover")) {
    return { escalate: true, reason: "human_handoff", confidence }
  }

  for (const group of keywordGroups) {
    if (group.keywords.some((keyword) => normalizedMessage.includes(keyword))) {
      return { escalate: true, reason: group.reason, confidence }
    }
  }

  if (typeof confidence === "number" && confidence < 0.7) {
    return { escalate: true, reason: "low_confidence", confidence }
  }

  if (normalizedIntent === "fallbackintent" || normalizedIntent === "fallback" || normalizedIntent.includes("fallback")) {
    return { escalate: true, reason: "fallback", confidence }
  }

  if ((failedResponseCount || 0) >= 3) {
    return { escalate: true, reason: "repeated_ai_failure", confidence }
  }

  return { escalate: false, reason: "ai_handled", confidence }
}

