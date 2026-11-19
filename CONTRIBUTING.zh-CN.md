# Contributing

[English](CONTRIBUTING.md) | **简体中文**

ASMR 以 ABBS 生成值为缺省值，手写 metadata 只覆盖写出的字段。源外条目必须显式标记 `external = true`。完整规则见 [缺省值与覆盖](docs/abbs-overlays.zh-CN.md)。

添加或修改软件 Metadata 前，请阅读
[`docs/maintainer-guide.zh-CN.md`](docs/maintainer-guide.zh-CN.md)。

权威手写输入集中在 `manual/`，示例使用 `examples/manual/`。`--root` 仍指向仓库根或
`examples`。CI 从 ABBS `stable` 生成缺省值，把合并后的 JSON 与媒体写入忽略的
`dist/v1/`。运行时状态由包管理服务提供。目录职责和输出限制见
[生成流程](docs/abbs-overlays.zh-CN.md)。

提交 PR 前至少运行：

```bash
make check ABBS_TREE=../aosc-os-abbs
make check-examples
make test
```

涉及 `installers`、下载域名、包名、发行方关系或风险声明的改动属于供应链敏感改动，
必须在 PR 中说明验证依据，并由项目维护者审核。

