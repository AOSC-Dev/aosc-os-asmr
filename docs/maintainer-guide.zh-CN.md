# ASMR 维护手册

[English](maintainer-guide.md) | **简体中文**

本手册面向负责把软件加入 AOSKA 搜索、详情页和推荐集合的维护者。

## 1. 基本原则

1. 每个应用只维护一份 `apps/<id>/app.toml`。
2. 不人工维护搜索索引、应用详情 JSON 或推荐项的名称和 Icon。
3. App ID 与 DEB 包名分离；通过 `installers` 建立绑定。
4. 不把已安装状态、当前版本或更新状态写入 ASMR。
5. 不在 Metadata 中保存脚本、Cookie、临时下载链接或网页爬取规则。
6. 不确定的声明使用 `unknown`，不要把未知写成 `false`。

## 2. 准备环境

维护工具只依赖 Python 3.11 及其标准库：

```bash
python3 --version
python3 tools/asmr.py check
```

推荐安装支持 Taplo/Even Better TOML 的编辑器插件。仓库中的 `taplo.toml` 和 `schemas/`
会提供字段补全和枚举提示。

## 3. 新增应用

### 3.1 AOSC 仓库软件

```bash
python3 tools/asmr.py new firefox \
  --kind aosc-repository \
  --category office
```

### 3.2 需要用户点击下载的 DEB

```bash
python3 tools/asmr.py new vendor-app \
  --kind browser-assisted-deb \
  --category communication
```

工具会创建：

```text
apps/<id>/app.toml
apps/<id>/description.zh-CN.md
apps/<id>/assets/icon.svg
apps/<id>/assets/hero.svg
```

模板中的 `TODO:` 字段必须全部替换，否则 CI 会失败。

## 4. 填写内容

### 身份和搜索

- `id` 一经发布不应修改；
- 名称、alias 和关键词应包含用户实际会搜索的中英文写法；
- `summary` 应是一句话，不要包含安装状态或版本号；
- 一个应用可以属于多个分类。

### 图片

- Icon 使用方形 SVG、PNG 或 WebP；
- Hero 建议接近 1280×480，并设置适合裁切的 focal point；
- Screenshot 应来自真实应用界面；
- 必须确认图片版权和再分发许可；
- 不要把下载页面截图当作软件截图。

### 发行方和声明

- `relationship = "upstream"` 表示来源是软件官方；
- AOSC 打包并不自动等于上游官方支持；
- `availability = "verified"` 必须有实际测试依据；
- 遥测或服务可用性不确定时填写 `unknown`；
- 区域限制、兼容层要求等应写入 `notes`。

## 5. 选择安装方式

### AOSC 仓库中已有包

使用 `aosc-repository`，包名必须是 omactl/oma 可识别的稳定名称：

```toml
[installers.package]
backend = "omactl"
names = ["firefox"]
```

### 上游允许直接下载

使用 `direct-deb`。维护者必须确认：

- 上游允许客户端自动访问；
- URL 不是一次性地址；
- 下载域名已加入允许列表；
- 包名和架构约束正确。

### 必须由用户在网页点击

使用 `browser-assisted-deb`。Metadata 只描述：

- 官方下载页面；
- 允许接收下载的 HTTPS Origin；
- 预期 DEB 包名和架构；
- 再分发、自动化和许可证政策。

不要填写页面 CSS selector，不要尝试绕过登录、验证码、许可证确认或上游访问限制。
AOSKA 应接收浏览器产生的下载文件，而不是记录临时 URL 后重新爬取。

### AOSKA 不能负责安装

使用 `external-link`，界面只提供“访问网站”或“打开下载页面”。

## 6. 添加到推荐集合

编辑 `collections/<collection>.toml`，仅增加应用 ID：

```toml
apps = ["firefox", "vendor-app"]
```

不要复制应用名称、简介或图片。搜索索引会自动包含所有 `listed + active` 应用，不需要
维护单独的 `index.toml`。

## 7. 本地检查

提交前运行：

```bash
make check
make check-examples
make test
```

如需查看生成物：

```bash
python3 tools/asmr.py build
find dist/v1 -type f
```

常见错误：

- App ID 与目录名不同；
- 使用了不存在的分类；
- 图片路径不存在或离开应用目录；
- 默认语言缺少名称、简介或截图 alt；
- Collection 引用了不存在的应用；
- browser-assisted installer 没有限制下载 Origin；
- Metadata 出现脚本或未替换的 `TODO:`。

## 8. PR 审核

PR 描述应包含：

- 软件官网和发行方；
- 为什么选择该 installer 类型；
- AOSC 仓库包名或外部 DEB control 信息；
- 可用性、兼容性和服务限制的验证依据；
- 图片来源和许可；
- 对下载或安装策略的任何变化。

修改以下字段时应视为供应链敏感：

- `installers`
- `publisher.relationship`
- 下载和跳转域名
- `expected_package_names`
- `processor` 或 `capability`

CI 通过只代表格式和静态安全约束正确，不代表软件值得信任，也不代替人工审核。

## 9. 定期维护

- 软件来源或下载域名变化时立即更新；
- 每次验证后更新应用和 disclosures 的 `reviewed_at`；
- 已不可用的软件使用 `lifecycle = "blocked"`；
- 暂时不希望出现在搜索中时使用 `visibility = "unlisted"`；
- 不删除已经发布的 ID 后复用于其他软件；
- 外部 DEB 更新时重新确认包名、架构、下载政策和服务可用性。
