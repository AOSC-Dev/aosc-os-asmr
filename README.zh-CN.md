# AOSC Software Manager Metadata Repository

[English](README.md) | **简体中文**

ASMR 是 AOSKA 使用的人工维护软件目录。维护者使用 TOML、Markdown 和媒体文件描述
应用；CI 校验源数据并生成只读 JSON Catalog。

ASMR 负责：

- 应用名称、简介、分类、搜索关键词和多语言内容；
- Icon、头图和截图；
- 发行方、支持关系、可用性和隐私/兼容性声明；
- AOSC 仓库包名或外部下载入口；
- 首页推荐等人工策划集合。

ASMR **不负责**已安装状态、当前版本、可升级状态、安装计划、操作进度或日志。这些运行
数据由 `omactl`/`oma` 提供。

`repository.toml` 只保存仓库级兼容策略，不保存应用目录。Catalog 索引、revision、
生成时间、文件清单和摘要全部由 CI 自动生成。

## 快速开始

要求 Python 3.11 或更新版本；没有第三方 Python 依赖。

```bash
# 创建应用模板
python3 tools/asmr.py new example-app \
  --kind aosc-repository \
  --category utilities

# 校验全部源数据
python3 tools/asmr.py check

# 构建 dist/v1 JSON Catalog
python3 tools/asmr.py build

# 运行测试
python3 -m unittest discover -s tests -v
```

也可以使用：

```bash
make check
make test
make build
```

完整流程见
[`docs/maintainer-guide.zh-CN.md`](docs/maintainer-guide.zh-CN.md)，字段约束见
[`docs/schema-v1.zh-CN.md`](docs/schema-v1.zh-CN.md)。

## 仓库结构

```text
apps/<id>/app.toml              应用结构化 Metadata
apps/<id>/description.*.md      长介绍
apps/<id>/assets/               Icon、头图和截图
collections/*.toml              推荐、装机必备等应用 ID 集合
taxonomy/categories.toml        分类定义
schemas/                        编辑器使用的 JSON Schema
tools/asmr.py                   new/check/build 维护工具
dist/v1/                        CI 生成物，不人工编辑
```

生产 Metadata 不应复制到手工索引。`index.json`、应用详情 JSON、集合和文件摘要清单均由
`asmr build` 自动生成。
