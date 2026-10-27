import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

// 部署参数由 CI 注入（见 .github/workflows/deploy.yml）：
//   SITE       最终访问域名，如 https://foo.github.io
//   PAGES_BASE 子路径，如 /lina-archive；部署在域名根路径时为 /
// 本地开发不设置时默认跑在 http://localhost:4321 根路径。
const site = process.env.SITE ?? "http://localhost:4321";
const base = process.env.PAGES_BASE ?? "/";

export default defineConfig({
  site,
  base,
  output: "static",
  integrations: [sitemap()],
  server: {
    host: true,
  },
});
