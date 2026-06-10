import { Badge, Button, Container, Heading, Text, toast } from "@medusajs/ui"
import { defineRouteConfig } from "@medusajs/admin-sdk"
import { useEffect, useMemo, useState } from "react"

type AIUsageTotal = {
  estimated_cost_usd: number
  request_count: number
  lex_requests: number
  lambda_invocations: number
  gemini_prompt_tokens: number
  gemini_completion_tokens: number
  gemini_total_tokens: number
}

type ProviderBreakdown = {
  provider: string
  estimated_cost_usd: number
  request_count: number
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
  duration_ms?: number
  memory_mb?: number
  confidence_score?: number
  usage_basis?: string
  cost_label?: string
}

type DimensionBreakdown = {
  channel?: string
  intent?: string | null
  conversation_id?: string
  customer_key?: string
  estimated_cost_usd: number
  request_count: number
  lex_cost_usd: number
  gemini_cost_usd: number
  lambda_cost_usd: number
  lex_requests: number
  lambda_invocations: number
  gemini_prompt_tokens: number
  gemini_completion_tokens: number
}

type CostByDay = {
  date: string
  cost_usd: number
  lex_requests: number
  gemini_prompt_tokens: number
  gemini_completion_tokens: number
  lambda_invocations: number
}

type MonthlyProjection = {
  month_start: string
  month_end: string
  elapsed_days: number
  days_in_month: number
  cost_to_date: number
  projected_cost_usd: number
  formula: string
  label: string
}

type AIUsageSummary = {
  label: string
  cost_label: string
  disclaimer: string
  total: AIUsageTotal
  by_provider: ProviderBreakdown[]
  by_channel: DimensionBreakdown[]
  by_intent: DimensionBreakdown[]
  top_conversations: DimensionBreakdown[]
  top_customers: DimensionBreakdown[]
  cost_by_day: CostByDay[]
  trends: {
    "7d": CostByDay[]
    "30d": CostByDay[]
    "90d": CostByDay[]
  }
  monthly_projection: MonthlyProjection
}

const formatUsd = (value?: number | null) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 4,
    maximumFractionDigits: 6,
  }).format(Number(value || 0))

const formatNumber = (value?: number | null) =>
  new Intl.NumberFormat("vi-VN").format(Number(value || 0))

const AI_COST_FALLBACK: AIUsageSummary = {
  label: "Estimated AI Cost",
  cost_label: "Estimated Cost",
  disclaimer:
    "Dữ liệu được tính toán từ request usage và bảng giá cấu hình, không phải hóa đơn thực tế từ AWS hoặc Google Cloud.",
  total: {
    estimated_cost_usd: 0,
    request_count: 0,
    lex_requests: 0,
    lambda_invocations: 0,
    gemini_prompt_tokens: 0,
    gemini_completion_tokens: 0,
    gemini_total_tokens: 0,
  },
  by_provider: [],
  by_channel: [],
  by_intent: [],
  top_conversations: [],
  top_customers: [],
  cost_by_day: [],
  trends: { "7d": [], "30d": [], "90d": [] },
  monthly_projection: {
    month_start: "",
    month_end: "",
    elapsed_days: 0,
    days_in_month: 0,
    cost_to_date: 0,
    projected_cost_usd: 0,
    formula: "projected_cost_usd = cost_to_date / elapsed_days * days_in_month",
    label: "Estimated monthly cost projection",
  },
}

const AICostPage = () => {
  const [data, setData] = useState<AIUsageSummary>(AI_COST_FALLBACK)
  const [loading, setLoading] = useState(true)
  const [trendDays, setTrendDays] = useState<7 | 30 | 90>(30)

  const loadSummary = async (nextTrendDays = trendDays) => {
    setLoading(true)
    try {
      const response = await fetch(`/admin/ai-usage/summary?trend_days=${nextTrendDays}`)
      const body = await response.json()
      if (!response.ok) {
        throw new Error(body?.error || "Failed to load AI cost summary")
      }
      setData({ ...AI_COST_FALLBACK, ...body })
    } catch (error) {
      toast.error("Không thể tải thống kê chi phí AI", {
        description: error instanceof Error ? error.message : "Unknown error",
      })
    } finally {
      setLoading(false)
    }
  }

  const refreshSnapshot = async () => {
    try {
      const response = await fetch("/admin/ai-usage/daily-snapshots/refresh", {
        method: "POST",
      })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.error || "Snapshot refresh failed")
      }
      await loadSummary()
      toast.success("Đã làm mới snapshot chi phí AI")
    } catch (error) {
      toast.error("Không thể làm mới snapshot", {
        description: error instanceof Error ? error.message : "Unknown error",
      })
    }
  }

  useEffect(() => {
    void loadSummary(trendDays)
  }, [])

  const trend = useMemo(
    () => data.cost_by_day || data.trends[`${trendDays}d`] || [],
    [data, trendDays],
  )

  const maxTrendCost = Math.max(...trend.map((item) => item.cost_usd), 0)

  return (
    <div className="flex min-h-[calc(100vh-120px)] flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <Heading level="h1" className="text-xl">
            Estimated AI Cost
          </Heading>
          <Text size="small" className="mt-1 text-ui-fg-muted">
            {data.disclaimer}
          </Text>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <div className="flex rounded-md border border-ui-border-base bg-ui-bg-field p-1">
            {[7, 30, 90].map((days) => (
              <button
                key={days}
                type="button"
                onClick={() => {
                  setTrendDays(days as 7 | 30 | 90)
                  void loadSummary(days as 7 | 30 | 90)
                }}
                className={`rounded px-3 py-1.5 text-sm font-medium ${
                  trendDays === days
                    ? "bg-ui-bg-base text-ui-fg-base shadow-borders-base"
                    : "text-ui-fg-muted"
                }`}
              >
                {days} ngày
              </button>
            ))}
          </div>
          <Button variant="secondary" onClick={refreshSnapshot}>
            Refresh snapshot
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <Metric title="Estimated Cost" value={formatUsd(data.total.estimated_cost_usd)} loading={loading} />
        <Metric title="Lex requests" value={formatNumber(data.total.lex_requests)} loading={loading} />
        <Metric title="Gemini tokens" value={formatNumber(data.total.gemini_total_tokens)} loading={loading} />
        <Metric title="Fulfillment invocations" value={formatNumber(data.total.lambda_invocations)} loading={loading} />
      </div>

      <div className="grid grid-cols-[1.2fr_0.8fr] gap-4">
        <Container className="overflow-hidden border border-ui-border-base bg-ui-bg-base p-0">
          <SectionHeader
            title={`Estimated cost trend ${trendDays} ngày`}
            description={data.monthly_projection.formula}
          />
          <div className="flex h-72 items-end gap-1 px-5 pb-5 pt-6">
            {trend.length ? (
              trend.map((item) => {
                const height = maxTrendCost > 0 ? Math.max(6, (item.cost_usd / maxTrendCost) * 210) : 6
                return (
                  <div key={item.date} className="flex min-w-0 flex-1 flex-col items-center gap-2">
                    <div className="flex h-[220px] w-full items-end">
                      <div
                        className="w-full rounded-t bg-ui-fg-interactive"
                        style={{ height }}
                        title={`${item.date}: ${formatUsd(item.cost_usd)}`}
                      />
                    </div>
                    <Text size="xsmall" className="truncate text-ui-fg-muted">
                      {item.date.slice(5)}
                    </Text>
                  </div>
                )
              })
            ) : (
              <div className="flex flex-1 items-center justify-center text-ui-fg-muted">
                <Text size="small">Chưa có dữ liệu trend</Text>
              </div>
            )}
          </div>
        </Container>

        <Container className="border border-ui-border-base bg-ui-bg-base p-0">
          <SectionHeader
            title="Dự báo tháng"
            description={`${data.monthly_projection.month_start || "-"} đến ${data.monthly_projection.month_end || "-"}`}
          />
          <div className="space-y-5 p-5">
            <div>
              <Text size="small" className="text-ui-fg-muted">
                Estimated cost to date
              </Text>
              <Text size="xlarge" weight="plus" className="mt-2">
                {formatUsd(data.monthly_projection.cost_to_date)}
              </Text>
            </div>
            <div>
              <Text size="small" className="text-ui-fg-muted">
                Estimated month-end cost
              </Text>
              <Text size="xlarge" weight="plus" className="mt-2">
                {formatUsd(data.monthly_projection.projected_cost_usd)}
              </Text>
            </div>
            <div className="rounded-md border border-ui-border-base bg-ui-bg-subtle p-3">
              <Text size="xsmall" className="text-ui-fg-muted">
                elapsed_days = {data.monthly_projection.elapsed_days || 0}, days_in_month ={" "}
                {data.monthly_projection.days_in_month || 0}
              </Text>
            </div>
          </div>
        </Container>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <BreakdownTable
          title="Provider"
          rows={data.by_provider.map((item) => ({
            key: providerDisplayName(item.provider),
            cost: item.estimated_cost_usd,
            meta: `${formatNumber(item.request_count)} requests · confidence ${item.confidence_score ?? "-"}%`,
            detail: item.usage_basis,
          }))}
        />
        <BreakdownTable
          title="Channel"
          rows={data.by_channel.map((item) => ({
            key: item.channel || "unknown",
            cost: item.estimated_cost_usd,
            meta: `${formatNumber(item.request_count)} requests`,
          }))}
        />
        <BreakdownTable
          title="Intent"
          rows={data.by_intent.map((item) => ({
            key: item.intent || "unknown",
            cost: item.estimated_cost_usd,
            meta: `Lex ${formatUsd(item.lex_cost_usd)} / Gemini ${formatUsd(item.gemini_cost_usd)}`,
          }))}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <CostLeaderTable title="Top conversations" rows={data.top_conversations} keyName="conversation_id" />
        <CostLeaderTable title="Top customers" rows={data.top_customers} keyName="customer_key" />
      </div>
    </div>
  )
}

const Metric = ({ title, value, loading }: { title: string; value: string; loading: boolean }) => (
  <Container className="border border-ui-border-base bg-ui-bg-base p-5">
    <Text size="small" className="text-ui-fg-muted">
      {title}
    </Text>
    <Text size="xlarge" weight="plus" className="mt-3">
      {loading ? "..." : value}
    </Text>
  </Container>
)

const SectionHeader = ({ title, description }: { title: string; description?: string }) => (
  <div className="border-b border-ui-border-base px-5 py-4">
    <Heading level="h2" className="text-base">
      {title}
    </Heading>
    {description && (
      <Text size="xsmall" className="mt-1 text-ui-fg-muted">
        {description}
      </Text>
    )}
  </div>
)

const BreakdownTable = ({
  title,
  rows,
}: {
  title: string
  rows: Array<{ key: string; cost: number; meta: string; detail?: string }>
}) => (
  <Container className="overflow-hidden border border-ui-border-base bg-ui-bg-base p-0">
    <SectionHeader title={title} />
    <div className="divide-y divide-ui-border-base">
      {rows.length ? (
        rows.slice(0, 8).map((row) => (
          <div key={row.key} className="flex items-center justify-between gap-3 px-5 py-3">
            <div className="min-w-0">
              <Text size="small" weight="plus" className="truncate">
                {row.key}
              </Text>
              <Text size="xsmall" className="mt-1 truncate text-ui-fg-muted">
                {row.meta}
              </Text>
              {row.detail && (
                <Text size="xsmall" className="mt-1 truncate text-ui-fg-subtle">
                  {row.detail}
                </Text>
              )}
            </div>
            <Badge color="blue" size="small">
              {formatUsd(row.cost)}
            </Badge>
          </div>
        ))
      ) : (
        <EmptyRows />
      )}
    </div>
  </Container>
)

const CostLeaderTable = ({
  title,
  rows,
  keyName,
}: {
  title: string
  rows: DimensionBreakdown[]
  keyName: "conversation_id" | "customer_key"
}) => (
  <Container className="overflow-hidden border border-ui-border-base bg-ui-bg-base p-0">
    <SectionHeader title={title} />
    <div className="divide-y divide-ui-border-base">
      {rows.length ? (
        rows.slice(0, 20).map((row) => {
          const label = String(row[keyName] || "unknown")
          return (
            <div key={label} className="grid grid-cols-[1fr_auto] gap-4 px-5 py-3">
              <div className="min-w-0">
                <Text size="small" weight="plus" className="truncate">
                  {label}
                </Text>
                <Text size="xsmall" className="mt-1 text-ui-fg-muted">
                  Lex {formatUsd(row.lex_cost_usd)} · Gemini {formatUsd(row.gemini_cost_usd)} · Fulfillment{" "}
                  {formatUsd(row.lambda_cost_usd)}
                </Text>
              </div>
              <Text size="small" weight="plus">
                {formatUsd(row.estimated_cost_usd)}
              </Text>
            </div>
          )
        })
      ) : (
        <EmptyRows />
      )}
    </div>
  </Container>
)

const EmptyRows = () => (
  <div className="px-5 py-8 text-center">
    <Text size="small" className="text-ui-fg-muted">
      Chưa có dữ liệu chi phí AI
    </Text>
  </div>
)

const providerDisplayName = (provider: string) => {
  if (provider === "LAMBDA") {
    return "Fulfillment"
  }
  return provider
}

const CostIcon = () => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M12 2v20" />
    <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7H14a3.5 3.5 0 0 1 0 7H6" />
  </svg>
)

export const config = defineRouteConfig({
  label: "Estimated AI Cost",
  icon: CostIcon,
})

export default AICostPage
