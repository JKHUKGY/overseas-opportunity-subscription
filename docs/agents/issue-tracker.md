# Issue tracker: Local Markdown

需求与工单作为长期项目记录保存在 .scratch/ 下。

## 文件约定

- 每个功能一个目录：`.scratch/<feature-slug>/`
- 需求规格：`.scratch/<feature-slug>/spec.md`
- 实施工单：`.scratch/<feature-slug>/issues/<NN>-<slug>.md`
- 每张工单单独一个文件，编号从 01 开始。
- 分诊状态写在文件顶部附近的 `Status:` 行，取值见 `triage-labels.md`。
- 评论与讨论追加在 `## Comments` 下。

## 技能操作

- “发布到任务跟踪系统”：在对应功能目录中创建文件，按需创建目录。
- “获取相关工单”：读取用户提供的路径；仅提供编号时，在对应功能目录内定位。

## Wayfinding operations

供 wayfinder 技能使用：

- 地图：`.scratch/<effort>/map.md`，包含 Notes、Decisions-so-far、Fog。
- 子工单：`.scratch/<effort>/issues/NN-<slug>.md`，正文记录问题。
- `Type:` 取值：research、prototype、grilling、task。
- 此流程的 `Status:` 使用 open、claimed、resolved，区别于分诊状态。
- 依赖写在 `Blocked by: NN, NN`；列出的工单全部 resolved 后解除阻塞。
- 下一项工作：按编号选择 open 且未被阻塞的工单。
- 领取：开始工作前设置 `Status: claimed` 并保存。
- 完成：在 `## Answer` 下追加答案，设置 `Status: resolved`，
  并将结论摘要与链接追加到地图的 Decisions-so-far。
