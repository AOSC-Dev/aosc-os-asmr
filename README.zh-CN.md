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
- 首页推荐等人工策划集合。

ASMR **不负责**已安装状态、当前版本、可升级状态、安装计划、操作进度或日志。这些运行
数据由 `omactl`/`oma` 提供。

`manual/repository.toml` 只保存仓库级兼容策略，不保存应用目录。Catalog 索引、revision、
生成时间、文件清单和摘要全部由 CI 自动生成。

权威手写输入集中在 `manual/`，示例使用 `examples/manual/`。`--root` 仍指向仓库根或
`examples`。本地构建写入 Git 忽略的 `dist/v1/`。CI 从 ABBS `stable` 生成缺省值，在临时目录中构建同一布局并上传 artifact。运行时状态由包管理服务提供。目录职责和输出限制见
[生成流程](docs/abbs-overlays.zh-CN.md)。

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
manual/collections/*.toml       人工策划的应用 ID 集合
manual/taxonomy/categories.toml 分类定义
examples/manual/               同布局的示例输入
schemas/                       编辑器使用的 JSON Schema
tools/asmr.py                   new/check/build 维护工具
dist/v1/                       生成的 JSON 和复制后的媒体
```

生产 Metadata 不应复制到手工索引。`index.json`、应用详情 JSON、集合和文件摘要清单均由
`asmr build` 自动生成。
