FROM node:22-bookworm-slim AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

FROM base AS builder
WORKDIR /app
COPY . .
RUN pnpm install --frozen-lockfile

ARG NEXT_PUBLIC_MEDUSA_BACKEND_URL=http://host.docker.internal:9000
ARG NEXT_PUBLIC_BASE_URL=http://localhost:8000
ARG NEXT_PUBLIC_CHAT_WS_URL=ws://host.docker.internal:9001

ENV NEXT_PUBLIC_MEDUSA_BACKEND_URL=${NEXT_PUBLIC_MEDUSA_BACKEND_URL}
ENV NEXT_PUBLIC_BASE_URL=${NEXT_PUBLIC_BASE_URL}
ENV NEXT_PUBLIC_CHAT_WS_URL=${NEXT_PUBLIC_CHAT_WS_URL}

RUN pnpm --filter @dtc/storefront build

FROM base AS runner
WORKDIR /app
COPY --from=builder /app /app

WORKDIR /app/apps/storefront
EXPOSE 8000

CMD ["pnpm", "start"]
