FROM node:22-bookworm-slim AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

# Install python and build dependencies for node-gyp (required by msgpackr-extract & bcrypt)
RUN apt-get update && apt-get install -y python3 make g++ && rm -rf /var/lib/apt/lists/*

FROM base AS builder
WORKDIR /app
ARG VITE_CHAT_WS_URL
ARG NEXT_PUBLIC_MEDUSA_BACKEND_URL
ARG NEXT_PUBLIC_BASE_URL
ENV VITE_CHAT_WS_URL=${VITE_CHAT_WS_URL}
ENV NEXT_PUBLIC_MEDUSA_BACKEND_URL=${NEXT_PUBLIC_MEDUSA_BACKEND_URL}
ENV NEXT_PUBLIC_BASE_URL=${NEXT_PUBLIC_BASE_URL}
# Copy the entire monorepo
COPY . .
RUN pnpm install --frozen-lockfile
WORKDIR /app/apps/backend
ENV NODE_OPTIONS=--max-old-space-size=4096
RUN pnpm run build
RUN mkdir -p public && cp -r .medusa/server/public/admin public/admin || true
FROM base AS runner
WORKDIR /app
# Copy the built monorepo
COPY --from=builder /app /app

WORKDIR /app/apps/backend
EXPOSE 9000 9001

# Start medusa
CMD ["pnpm", "start"]
