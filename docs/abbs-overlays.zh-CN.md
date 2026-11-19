# ABBS 缺省值与手写覆盖

ASMR 从 ABBS 生成缺省目录，再合并 `manual/apps/<id>/app.toml` 中写出的字段。
维护者可以只维护一项简介或媒体，省略字段沿用生成值。

| 输入情况 | 结果 |
| --- | --- |
| ABBS 有包，没有手写文件 | 生成目录条目 |
| ABBS 有包，有手写文件 | 手写字段覆盖对应缺省值 |
| ABBS 无包，手写 `external = true` | 校验为外部条目 |
| ABBS 无包，未标记 external | 校验失败，检查包名及提取诊断 |

所有权威手写输入位于 `manual/`。外部应用和仓库包的覆盖文件都放在
`manual/apps/<id>/app.toml`，CI 从 ABBS `stable` 获取生成输入，在临时目录构建并上传 artifact。本地默认将 JSON 与媒体副本写入 Git 忽略的 `dist/v1/`。实际安装状态、候选版本和操作结果由客户端查询包管理服务。

`--root` 指向仓库根目录；`--root examples` 读取 `examples/manual/`。
在仓库内，`--output` 只允许指向 `dist` 或其子目录。也可以指定仓库外的临时输出目录。
客户端继续读取 `dist/v1/index.json`、`apps/<id>.json`、集合和 manifest，输入目录调整不改变发布布局。

## 合并规则

表按字段递归合并，列表整体替换。`keywords = []` 或 `media.screenshots = []`
明确清空对应列表。合并结果仍须通过字段类型、分类、媒体路径和安装入口校验。
`external` 必须是布尔值。`external = true` 与源内包或仓库安装入口冲突时会报错。

例如，`manual/apps/firefox/app.toml` 可以只写：

```toml
[locales."zh-CN"]
summary = "网页浏览器"
```

应用 ID 可以与包名不同。此时使用 `aosc-repository` 安装入口的
`package.names` 明确关联包。`installers` 是列表，覆盖它时须填写完整的安装入口。
外部条目需要显式 `external = true` 及适合其来源的安装或网页入口；标记本身不会赋予
自动下载或安装能力。

## 自动生成的信息

生成器从普通 `autobuild/defines` 和分包 `NN-name/defines` 读取实际 `PKGNAME`、
`PKGDES`、`PKGSEC`，记录配方路径和 ABBS 提交。可解析的 `spec` 版本和修订保存在
原始包事实中。包分类匹配商店分类 ID 时直接沿用，其他包归入“未分类”。新增语言只提供名称时，客户端可回退到默认英文简介。媒体、长介绍、审核信息可省略。
生成器不会自动宣称软件已测试或获得上游支持。

当前提取器支持静态字面量赋值。复杂表达式、架构覆盖、重复包名和无法可靠读取的配方
会产生提取诊断。CI 产物中的 `abbs-packages.json` 保留这些诊断；引用无法解析的包会
使目录构建失败。ABBS 配方版本描述源码树，具体架构的已发布版本仍由包管理查询确定。

## 构建与来源记录

```bash
python3 tools/asmr.py check --abbs-tree ../aosc-os-abbs
python3 tools/asmr.py build --abbs-tree ../aosc-os-abbs --output dist/v1
```

CI 检出 ABBS `stable`，将实际 Git 提交号写入 manifest 的 `abbs_source_commit`。
`abbs_inventory` 指向有 SHA-256 摘要的 `abbs-packages.json`。应用详情中的 `abbs`
保存原始包事实，手写展示字段不会覆盖来源记录。目录 revision 包含 ABBS 输入。
CI 在推送、PR、手动触发及定时任务中生成 artifact，生产签名发布仍需独立配置。

## 官方参考

- [软件包维护基础教程](https://wiki.aosc.io/zh/developer/packaging/basics/)
- [软件包样式指南](https://wiki.aosc.io/zh/developer/packaging/package-styling-manual/)
- [APML](https://wiki.aosc.io/developer/automation/apml/)
- [FAIL_ARCH](https://wiki.aosc.io/zh/developer/packaging/fail-arch/)
