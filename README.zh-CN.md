# AOSC Software Manager Metadata Repository

[English](README.md) | **简体中文**

ASMR 以 ABBS 生成值为缺省值，手写 metadata 只覆盖写出的字段。源外条目必须显式标记 `external = true`。完整规则见 [缺省值与覆盖](docs/abbs-overlays.zh-CN.md)。

维护者使用 TOML、Markdown 和媒体文件补充应用信息；CI 从 ABBS 生成缺省目录，
合并手写字段并生成只读 JSON Catalog。

ASMR 负责：

- 应用名称、简介、分类、搜索关键词和多语言内容；
- Icon、头图和截图；
- 发行方、支持关系、可用性和隐私/兼容性声明；
- AOSC 仓库包名或外部下载入口；
- 首页头图、装机必备的应用及其顺序、技巧指南链接。

Aoska 通过 oma 的 D-Bus 服务 amo（`io.aosc.Amo`）查询软件包状态、已安装版本和候选版本，
并获取事务计划、进度和结果。

`manual/repository.toml` 只保存仓库级兼容策略，不保存应用目录。Catalog 索引、revision、
生成时间、文件清单和摘要全部由 CI 自动生成。

权威手写输入集中在 `manual/`，示例使用 `examples/manual/`。`--root` 仍指向仓库根或
`examples`。本地构建写入 Git 忽略的 `dist/v1/`。CI 从 ABBS `stable` 生成缺省值，在临时目录中构建同一布局并上传 artifact。运行时状态由包管理服务提供。目录职责和输出限制见
[生成流程](docs/abbs-overlays.zh-CN.md)。

## 目录渠道

| 渠道 | 目录地址 | 发布方式 |
| --- | --- | --- |
| dev | `https://aosc-dev.github.io/aosc-os-asmr/v1/` | `main` 上的推送、定时构建或手动运行通过验证后，CI 将 ABBS 目录发布到 GitHub Pages。 |
| stable | `https://repo.aosc.io/asmr/v1/` | AOSC 官方仓库的暂定地址，待上线。 |

首次发布 dev 时，在仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。在 `main` 运行 CI，部署完成后检查站点上的 `v1/index.json`。PR 和其他分支只生成测试产物。示例目录保留在常规 CI artifact 中。

## 快速开始

要求 Python 3.11 或更新版本；没有第三方 Python 依赖。

```bash
# 创建应用模板
python3 tools/asmr.py new example-app \
  --kind aosc-repository \
  --category utilities

# 校验全部源数据
python3 tools/asmr.py check --abbs-tree ../aosc-os-abbs

# 构建 dist/v1 JSON Catalog
python3 tools/asmr.py build --abbs-tree ../aosc-os-abbs

# 运行测试
python3 -m unittest discover -s tests -v
```

也可以使用：

```bash
make check ABBS_TREE=../aosc-os-abbs
make test
make build ABBS_TREE=../aosc-os-abbs
```

完整流程见
[`docs/maintainer-guide.zh-CN.md`](docs/maintainer-guide.zh-CN.md)，字段约束见
[`docs/schema-v1.zh-CN.md`](docs/schema-v1.zh-CN.md)。

## 仓库结构

```text
manual/repository.toml          仓库兼容策略
manual/apps/<id>/app.toml       手写字段覆盖与外部应用
manual/apps/<id>/description.*.md  长介绍
manual/apps/<id>/assets/        Icon、头图和截图
manual/collections/*.toml       有序应用集合，含装机必备 essentials.toml
manual/homepage/hero.toml       首页头图的文案、图片路径和跳转目标
manual/homepage/assets/         首页头图素材
manual/homepage/guides.toml     按展示顺序排列的技巧指南
manual/taxonomy/categories.toml 分类定义
examples/manual/               同布局的示例输入
schemas/                       编辑器使用的 JSON Schema
tools/asmr.py                   new/check/build 维护工具
dist/v1/                       生成的 JSON 和复制后的媒体
```

生产 Metadata 不应复制到手工索引。`index.json`、`homepage.json`、应用详情 JSON、集合和文件摘要清单均由
`asmr build` 自动生成。
