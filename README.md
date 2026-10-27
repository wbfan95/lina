# 李娜作品档案（lina-archive）

以歌手李娜为核心的作品资料站：歌曲条目、歌词、曲谱扫描、相关人物、影视作品与年表。
纯静态站点，基于 [Astro 5](https://astro.build) 构建，无数据库、无服务端，可整体托管在 GitHub Pages 等静态服务上。

## 本地开发

```bash
npm ci          # 安装依赖（Node.js >= 20）
npm run dev     # 开发服务器，默认 http://localhost:4321
npm run build   # 内容校验 + 静态构建到 dist/
npm run preview # 本地预览构建产物
```

## 内容结构

```text
src/content/
  songs/    每首歌一个 JSON（id、title、pinyin、year、work、credits、lyrics、scores…）
  scores/   曲谱扫描图，目录名 = 歌曲 id，如 scores/青藏高原/01.jpg
  people/   人物资料 JSON
```

- 字段与排序约定见 `docs/song-json-order.json`，内容模型见 `docs/content-model.md`。
- 新增歌曲：在 `songs/` 放 JSON、在 `scores/<id>/` 放扫描图，页面与索引在构建时自动生成。

## 内容校验

`npm run build` 会先执行 `npm run validate`（`tools/validate_content.mjs`），校验：

- 歌曲 `scores` 声明的每张图都真实存在；
- 每个 `scores/` 目录都有对应 id 的歌曲（无孤儿目录）；
- id 唯一、与文件名一致、年份合理、视频链接为 http(s)。

构建在任何数据错配时会直接失败，避免页面静默丢内容。

## 部署（GitHub Pages）

`.github/workflows/deploy.yml` 在推送到 `main` 时自动构建并发布：

1. 仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**；
2. push 到 `main` 即自动部署，站点地址为 `https://<用户名>.github.io/<仓库名>/`；
3. 若仓库名就是 `<用户名>.github.io`（用户主站），workflow 会自动以根路径部署，无需改配置；
4. 使用自定义域名时，把 workflow 中 `SITE` 环境变量改为你的域名，并在仓库里添加 `public/CNAME`。

构建参数通过环境变量注入，本地也可模拟：

```bash
SITE=https://foo.github.io PAGES_BASE=/lina-archive npm run build
```

## 许可与内容说明

- 站点代码以 [MIT](./LICENSE) 许可开源。
- **歌词与曲谱扫描件的版权归原词曲作者、出版方所有**。本项目仅作资料整理与学习研究之用；
  如你是权利人并要求移除相关内容，请提 issue，我们会及时处理。
- 部分资料整理自公开网页（如百度贴吧），原始出处逐步补录在 `sources` 内容板块。
