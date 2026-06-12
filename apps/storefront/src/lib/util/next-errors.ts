/**
 * Checks if an error is an internal Next.js control flow exception
 * (e.g. Dynamic Server Usage, Redirects, or Not Found triggers).
 * These errors should be rethrown to let Next.js handle them.
 */
export function isNextInternalError(error: unknown): boolean {
  if (typeof error !== "object" || error === null) {
    return false
  }

  const err = error as Record<string, any>
  const digest = err.digest
  const message = err.message || ""

  return (
    digest === "DYNAMIC_SERVER_USAGE" ||
    digest?.startsWith("NEXT_REDIRECT") ||
    digest?.startsWith("NEXT_NOT_FOUND") ||
    message.includes("DYNAMIC_SERVER_USAGE") ||
    message.includes("DynamicServerError")
  )
}

/**
 * Rethrows the error if it is an internal Next.js control flow exception.
 */
export function rethrowNextInternalError(error: unknown): void {
  if (isNextInternalError(error)) {
    throw error
  }
}
