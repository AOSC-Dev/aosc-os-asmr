## 变更内容 / Changes

<!-- 说明新增或修改了哪些应用、集合、分类或工具。
Describe the applications, collections, categories, or tools changed by this PR. -->

## 来源与验证 / Source and verification

- 软件官网 / Official website:
- 发行方 / Publisher:
- Installer 类型 / Installer type:
- ABBS 提交 / ABBS commit:
- 手写覆盖路径 / Handwritten overlay path (`manual/apps/<id>/app.toml`):
- 外部条目标记 / External entry marker (`external = true` where absent from ABBS):
- 包名或 DEB control 信息 / Package name or DEB control information:
- 可用性验证 / Availability verification:
- 图片来源与许可 / Media source and license:

## 审核清单 / Review checklist

- [ ] `python3 tools/asmr.py check --abbs-tree ../aosc-os-abbs` passes
- [ ] `python3 -m unittest discover -s tests -v` passes
- [ ] App ID 稳定且不依赖显示名称 / The app ID is stable and independent of its display name
- [ ] 手写输入位于 `manual/`，生成物位于忽略的 `dist/v1/` / Handwritten inputs are under `manual/`; generated artifacts are under ignored `dist/v1/`
- [ ] 没有临时 URL、Cookie、Token、脚本或爬取规则 / No temporary URL, cookie, token, script, or scraping rule is present
- [ ] 合并后的默认语言和已提供媒体的 alt 校验通过 / Default-locale content and supplied media alt text pass validation after merging
- [ ] “未知”没有写成“没有” / Unknown disclosures are not represented as absent
- [ ] 外部下载已限制 HTTPS Origin / External downloads are restricted to HTTPS origins
- [ ] 包名已经核对 / Package names have been verified

## 供应链敏感变更 / Supply-chain-sensitive changes

<!-- 如修改 installer、域名、包名、processor 或 capability，请说明风险和审核依据。
Explain the risk and review evidence for changes to installers, origins, package names,
processors, or capabilities. -->

