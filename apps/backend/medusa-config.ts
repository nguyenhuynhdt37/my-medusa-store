import { loadEnv, defineConfig } from '@medusajs/framework/utils'

loadEnv(process.env.NODE_ENV || 'development', process.cwd())

const cookieOptions =
  process.env.COOKIE_SECURE || process.env.COOKIE_SAME_SITE
    ? {
      sameSite: (process.env.COOKIE_SAME_SITE || "lax") as
        | "lax"
        | "strict"
        | "none",
      secure: process.env.COOKIE_SECURE === "true",
    }
    : undefined

const viteAllowedHosts = Array.from(
  new Set(
    [
      "localhost",
      "127.0.0.1",
      process.env.PUBLIC_HOST,
      process.env.NEXT_PUBLIC_MEDUSA_BACKEND_URL
        ? new URL(process.env.NEXT_PUBLIC_MEDUSA_BACKEND_URL).host
        : undefined,
    ].filter(Boolean) as string[]
  )
)

module.exports = defineConfig({
  projectConfig: {
    databaseUrl: process.env.DATABASE_URL,
    databaseDriverOptions: {
      pool: {
        min: 0,
        max: 10,
      },
    },
    redisUrl: process.env.REDIS_URL,
    http: {
      storeCors: process.env.STORE_CORS!,
      adminCors: process.env.ADMIN_CORS!,
      authCors: process.env.AUTH_CORS!,
      jwtSecret: process.env.JWT_SECRET || "supersecret",
      cookieSecret: process.env.COOKIE_SECRET || "supersecret",
    },
    cookieOptions,
  },
  admin: {
    disable: process.env.DISABLE_MEDUSA_ADMIN === "true",
    backendUrl: process.env.NEXT_PUBLIC_MEDUSA_BACKEND_URL,
    storefrontUrl: process.env.NEXT_PUBLIC_BASE_URL,
    vite: (config) => {
      if (process.env.NODE_ENV === "production") {
        return {}
      }

      const hmrPortRaw = process.env.MEDUSA_ADMIN_HMR_PORT
      const hmrPort = Number(hmrPortRaw ?? 0)

      // Nếu env không set (hoặc bị set 0), mặc định dùng 9000 để match port backend map ra host.
      const resolvedHmrPort = hmrPort > 0 ? hmrPort : 9000

      // Override HMR config đầy đủ để tránh Vite client fallback về port mặc định (7001)
      return {
        server: {
          hmr: {
            ...(typeof config.server?.hmr === "object" ? config.server.hmr : {}),
            port: resolvedHmrPort,
            clientPort: resolvedHmrPort,

            // Admin đang chạy với base path "/app", nên websocket cũng phải gắn cùng path đó.
            // Vite sẽ ghép "/app/" vào socket url.
            path: "/app/",

            // protocol: nếu HTTPS thì dùng wss, còn lại dùng ws.
            // (Trong dev thường là http)
            protocol:
              (process.env.HTTPS === "true" || process.env.VITE_HTTPS === "true"
                ? "wss"
                : "ws") as any,
          },

          allowedHosts: [
            ...new Set([
              ...viteAllowedHosts,
              ...(
                Array.isArray(config.server?.allowedHosts)
                  ? config.server.allowedHosts
                  : []
              ),
            ]),
          ],
        },
      }
    },
  },
  modules: [
    {
      resolve: "./src/modules/chat",
    },
  ],
})
