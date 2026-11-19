# ASMR Metadata Schema v1

[English](schema-v1.md) | **简体中文**

使用 ABBS 构建时，手写文件是部分覆盖层。下列完整字段约束作用于合并结果；覆盖规则及缺省字段见 [ABBS 缺省值与手写覆盖](abbs-overlays.zh-CN.md)。外部条目必须添加 `external = true`。

本文档描述 ASMR v1 的源文件和生成物约束。规范实现是 `tools/asmr.py`；`schemas/` 中的
JSON Schema 用于编辑器补全。

## 1. 权威边界

| 信息 | 权威来源 |
| --- | --- |
| 名称、介绍、分类、媒体、链接 | ASMR |
| 发行方关系和编辑性声明 | ASMR |
| Catalog 中可用的安装入口 | ASMR |
| AOSC 仓库包名或外部 DEB 预期包名 | ASMR |
| 已安装、可升级、当前版本和实际安装大小 | omactl/oma |
| 外部 DEB 的真实版本、架构和校验值 | 下载后的制品 |
| 操作计划、状态、日志和结果 | omactl |

应用 ID 是稳定的 Catalog 身份，不要求等于 DEB 包名。

## 2. 应用文件

每个应用位于 `apps/<id>/app.toml`。`id` 必须与目录名一致，只能包含小写字母、数字、
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

### 3.1 `aosc-repository`

软件由 AOSC 仓库提供，通过 omactl 按稳定包名安装和升级。

```toml
[[installers]]
id = "aosc"
kind = "aosc-repository"
priority = 100
architectures = ["amd64", "arm64"]
update_policy = "managed"

[installers.package]
backend = "omactl"
names = ["example-app"]
```

不得同时定义 `acquisition`、`artifact` 或本地安装处理器。

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

[installers.install]
backend = "omactl"
capability = "run.install-local.v1"
processor = "deb-local-v1"
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

该类型不得定义 `package`、`artifact` 或 `install`。

## 4. Collections

`collections/<id>.toml` 只维护应用 ID，不复制名称、简介或媒体：

```toml
schema_version = 1
id = "essentials"
visibility = "listed"
apps = ["firefox", "vlc"]

[locales."zh-CN"]
title = "装机必备"
```

构建器会拒绝重复 ID 和不存在的应用。

## 5. 生成物

`asmr build` 生成：

```text
dist/v1/index.json
dist/v1/collections.json
dist/v1/apps/<id>.json
dist/v1/apps/<id>/assets/
dist/v1/manifest.json
```

`manifest.json` 记录由全部原始 Metadata 自动计算的 `catalog_revision`、最低客户端版本、
源 Git 提交、生成时间，以及每个生成文件的 SHA-256 和字节数。生成物不得人工编辑或
作为源 Metadata。

生产发布还需要对 manifest 进行固定公钥签名；签名和 stable 发布不属于当前验证 CI。
