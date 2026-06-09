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
    keywords: [
      "gặp nhân viên",
      "gap nhan vien",
      "gặp nhân sự",
      "gap nhan su",
      "gặp hỗ trợ",
      "gap ho tro",
      "gặp người thật",
      "gap nguoi that",
      "gặp admin",
      "gap admin",
      "hỗ trợ trực tiếp",
      "ho tro truc tiep",
      "nói chuyện với nhân viên",
      "noi chuyen voi nhan vien",
      "nhân viên đâu",
      "nhan vien dau",
      "admin đâu",
      "admin dau",
      "người thật đâu",
      "nguoi that dau",
      "cho gặp người",
      "cho gap nguoi",
    ],
  },
]

const normalize = (value?: string | null) => {
  return (value || "")
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
}

const levenshteinDistance = (a: string, b: string) => {
  const matrix = Array.from({ length: a.length + 1 }, (_, row) => [row])

  for (let col = 1; col <= b.length; col++) {
    matrix[0][col] = col
  }

  for (let row = 1; row <= a.length; row++) {
    for (let col = 1; col <= b.length; col++) {
      matrix[row][col] = a[row - 1] === b[col - 1]
        ? matrix[row - 1][col - 1]
        : Math.min(
          matrix[row - 1][col - 1] + 1,
          matrix[row][col - 1] + 1,
          matrix[row - 1][col] + 1
        )
    }
  }

  return matrix[a.length][b.length]
}

const similarity = (a: string, b: string) => {
  const maxLength = Math.max(a.length, b.length)
  if (!maxLength) return 1
  return 1 - levenshteinDistance(a, b) / maxLength
}

const isFuzzyKeywordMatch = (message: string, keyword: string) => {
  const normalizedKeyword = normalize(keyword)
  if (message.includes(normalizedKeyword)) {
    return true
  }

  const messageWords = message.split(" ")
  const keywordWords = normalizedKeyword.split(" ")
  const phraseSize = keywordWords.length

  for (let index = 0; index <= messageWords.length - phraseSize; index++) {
    const candidate = messageWords.slice(index, index + phraseSize).join(" ")
    if (similarity(candidate, normalizedKeyword) >= 0.78) {
      return true
    }
  }

  const hasHumanTarget = ["nhan vien", "admin", "nguoi that", "ho tro"].some((target) =>
    message.includes(target) || similarity(message, target) >= 0.7
  )
  const hasHandoffVerb = ["gap", "can", "muon", "noi chuyen", "cho gap", "dau"].some((verb) => message.includes(verb))

  return hasHumanTarget && hasHandoffVerb
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
    if (group.keywords.some((keyword) => isFuzzyKeywordMatch(normalizedMessage, keyword))) {
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
