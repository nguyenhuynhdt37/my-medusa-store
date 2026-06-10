import { loadEnv, defineConfig } from '@medusajs/framework/utils'

loadEnv(process.env.NODE_ENV || 'development', process.cwd())

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
    }
  },
  admin: {
    disable: process.env.DISABLE_MEDUSA_ADMIN === "true",
  },
  // admin: {
  //   vite: (config) => {
  //     config.server = {
  //       ...config.server,
  //       hmr: {
  //         clientPort: 9000,
  //       }
  //     }
  //     return config
  //   }
  // },
  modules: [
    {
      resolve: "./src/modules/chat",
    },
  ],
})
