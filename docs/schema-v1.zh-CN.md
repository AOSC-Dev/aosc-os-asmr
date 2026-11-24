# ASMR Metadata Schema v1

[English](schema-v1.md) | **简体中文**

使用 ABBS 构建时，手写文件是部分覆盖层。下列完整字段约束作用于合并结果；覆盖规则及缺省字段见 [ABBS 缺省值与手写覆盖](abbs-overlays.zh-CN.md)。外部条目必须添加 `external = true`。

本文档描述 ASMR v1 的源文件和生成物约束。规范实现是 `tools/asmr.py`；`schemas/` 中的
JSON Schema 用于编辑器补全。

权威手写输入集中在 `manual/`，示例使用 `examples/manual/`。`--root` 仍指向仓库根或
`examples`。CI 从 ABBS `stable` 生成缺省值，把合并后的 JSON 与媒体写入忽略的
`dist/v1/`。运行时状态由包管理服务提供。目录职责和输出限制见
[生成流程](abbs-overlays.zh-CN.md)。

## 1. 权威边界

| 信息 | 权威来源 |
| --- | --- |
| 名称、介绍、分类、媒体、链接 | ASMR |
| 发行方关系和编辑性声明 | ASMR |
| Catalog 中可用的安装入口 | ASMR |
| AOSC 仓库包名或外部 DEB 预期包名 | ASMR |
| 软件包状态、已安装版本和候选版本 | amo |
| 外部 DEB 的真实版本、架构和校验值 | 下载后的制品 |
| 事务计划、进度和结果 | amo |

应用 ID 是稳定的 Catalog 身份，不要求等于 DEB 包名。

## 2. 应用文件

每个应用位于 `manual/apps/<id>/app.toml`。`id` 必须与目录名一致，只能包含小写字母、数字、
点、下划线、加号和连字符。

完整手写条目（含外部条目）的必填顶层字段：

- `schema_version = 1`
- `id`
- `visibility`: `listed`、`unlisted`、`hidden`
- `lifecycle`: `active`、`deprecated`、`blocked`
- `default_locale`
- `categories`
- `maintainers`
- `reviewed_at`
- `locales`
- `media`
- `publisher`
- `disclosures`
- `installers`

只有 `visibility = "listed"` 且 `lifecycle = "active"` 的应用会进入搜索索引。

### 2.1 多语言内容

```toml
[locales."zh-CN"]
name = "示例软件"
summary = "一句简短介绍"
description = "description.zh-CN.md"
```

`description` 必须指向应用目录内的 Markdown 文件。构建时 Markdown 内容会写入应用详情
JSON，不会把本地文件路径暴露给客户端。

### 2.2 媒体

```toml
[media]
icon = "assets/icon.svg"
hero = "assets/hero.webp"
hero_focal_point = [0.7, 0.5]

[[media.screenshots]]
path = "assets/screenshots/main.webp"
alt = { zh-CN = "软件主界面", en = "Main window" }
```

- 完整手写条目必填 `icon` 和 `hero`，ABBS 生成条目可以省略；
- 支持 AVIF、JPEG、PNG、SVG、WebP；
- 单个源文件不得超过 10 MiB；
- 路径不得离开应用目录；
- Screenshot 的 `alt` 至少包含默认语言；
- `hero_focal_point` 是从左上角起算的 `[x, y]`，取值范围为 0 到 1。

### 2.3 编辑性声明

```toml
[disclosures]
availability = "verified"
runtime = "native"
telemetry = "unknown"
service = "limited"
support = "upstream"
reviewed_at = 2026-07-23
notes = []
```

使用枚举而不是布尔值，以区分“没有”和“未知”。

## 3. Installer 类型

两种外部 DEB 入口都只描述如何获取文件，以及校验 DEB control 字段时预期的包名和架构。

### 3.1 `aosc-repository`

Aoska 按 AOSC 仓库包名通过 amo 安装和升级软件。

```toml
[[installers]]
id = "aosc"
kind = "aosc-repository"
priority = 100
architectures = ["amd64", "arm64"]
update_policy = "managed"

[installers.package]
backend = "amo"
names = ["example-app"]
```

软件包由仓库提供，省略 `acquisition` 和 `artifact`。

### 3.2 `direct-deb`

仅用于上游允许客户端直接访问稳定 DEB URL 的情况。

- `policy.automation` 必须为 `automatic`；
- 必须限制 `allowed_download_origins`；
- 最终 URL 不得持久化；
- 下载后仍需验证 DEB control 字段。

### 3.3 `browser-assisted-deb`

用于上游要求用户本人打开网站并点击下载的情况。

```toml
[[installers]]
id = "upstream-deb"
kind = "browser-assisted-deb"
priority = 100
architectures = ["amd64"]
update_policy = "repeat-acquisition"

[installers.policy]
redistribution = "forbidden"
automation = "user-mediated"
license_acceptance = "upstream-page"

[installers.acquisition]
landing_url = "https://vendor.example/download"
user_interaction = "required"
allowed_download_origins = ["https://download.vendor.example"]
persist_final_url = false

[installers.artifact]
format = "deb"
expected_package_names = ["example-app"]
architectures = ["amd64"]
version_source = "deb-control"
```

Metadata 不得包含网页选择器、爬取规则、Cookie、临时 Token、Shell 命令或自动点击脚本。

### 3.4 `external-link`

只能打开外部网页，AOSKA 不获取或安装制品：

```toml
[[installers]]
id = "upstream"
kind = "external-link"
priority = 100
architectures = []
update_policy = "external"

[installers.acquisition]
landing_url = "https://vendor.example/download"
```

该类型使用网页入口，省略 `package` 和 `artifact`。

## 4. Collections

`manual/collections/<id>.toml` 只维护应用 ID，不复制名称、简介或媒体：

```toml
schema_version = 1
id = "essentials"
visibility = "listed"
apps = ["firefox", "vlc"]

[locales."zh-CN"]
title = "装机必备"
```

构建器会拒绝重复 ID 和不存在的应用。

## 5. 首页

首页包含一组可切换的头图、一个装机必备集合和一组有序的技巧指南。各栏目独立维护。

| 源文件 | 字段 |
| --- | --- |
| `manual/homepage/hero.toml` | `schema_version = 1` 和按展示顺序填写的 `[[banners]]`。每张头图含 `target`、`locales`、`image`。空列表写作 `banners = []`。 |
| `manual/collections/essentials.toml` | 使用第 4 节的集合格式。首页引用 ID 为 `essentials` 且 `visibility = "listed"` 的集合，按 `apps` 数组顺序展示。 |
| `manual/homepage/guides.toml` | `schema_version = 1` 和有序数组 `items`。可选的 `more_url` 指向指南总目录。每个 `[[items]]` 条目包括唯一的 `id`、`date`、`url` 和 `locales`。空列表写作 `items = []`。 |

每张头图的 `target` 表只能填写一个键。`app` 指向应用 ID，`collection` 指向集合 ID，
`url` 指向 HTTPS 网页。构建器会在合并后的目录中校验引用的 ID。
专用图片放在 `manual/homepage/assets/`，对应字段写作 `image = "assets/<文件名>"`。
图片格式和大小限制见第 2.2 节。若推荐的应用已有会随目录发布的 `media.hero`，
省略 `image` 即可使用该图。原有的顶层 `target`、`locales` 和可选 `image` 写法
仍可用于单张头图。

头图和每篇指南都要提供仓库默认语言的 `locales.<语言>.title`。每种翻译必填 `title`，
可选填 `subtitle`。指南 ID 的可用字符与应用 ID 相同。`date` 填写 ASMR 收录该指南的日期，
格式为 `YYYY-MM-DD`。构建器保留手写顺序。指南的 `url` 和总目录的 `more_url` 均使用
HTTPS。完整示例见[首页头图](../manual/homepage/hero.toml)和[指南清单](../manual/homepage/guides.toml)。

## 6. 生成物

`asmr build` 生成：

```text
dist/v1/index.json
dist/v1/collections.json
dist/v1/homepage.json
dist/v1/homepage/assets/
dist/v1/apps/<id>.json
dist/v1/apps/<id>/assets/
dist/v1/manifest.json
```

客户端读取 `index.json` 的 `homepage` 字段，即可找到同一次构建的
`homepage.json`。即使各栏目都没有内容，构建器也会生成该文件：

```json
{"schema_version": 1, "hero": null, "banners": [], "essentials": null, "guides": {"items": []}}
```

`banners` 按 `hero.toml` 中的顺序排列。每项含 `target`、`locales` 和相对于
`dist/v1/` 的图片路径 `image`。`hero` 保留第一张供旧客户端读取，空列表时为 `null`。
专用图使用 `homepage/assets/…`，复用的应用图沿用 `apps/<id>/assets/…`。
`essentials` 是供客户端在 `collections.json` 中查找的集合 ID，集合缺失或隐藏时值为 `null`。
`guides.items` 保留源文件中的字段和顺序，日期以字符串输出。填写的总目录链接输出到
`guides.more_url`。首页 JSON 和发布的图片都纳入 manifest 的文件清单。

`manifest.json` 记录由全部原始 Metadata 自动计算的 `catalog_revision`、最低客户端版本、
源 Git 提交、生成时间，以及每个生成文件的 SHA-256 和字节数。生成物不得人工编辑或
作为源 Metadata。

生产发布还需要对 manifest 进行固定公钥签名；签名和 stable 发布不属于当前验证 CI。
