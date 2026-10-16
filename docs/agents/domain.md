# Domain Docs

本项目采用 single-context 布局。

## 探索前读取

- 根目录 `CONTEXT.md`：领域术语及定义。
- `docs/adr/`：与当前工作相关的架构决策记录。

文件或目录不存在时，直接继续。
由 domain-modeling 技能在术语或决策明确后按需创建。

## 术语使用

工单、方案、假设和测试中出现领域概念时，采用 CONTEXT.md 的定义，
遵守其中的 Avoid 约定。

遇到词汇表未覆盖的概念时，先检查已有术语是否适用；
确有缺口则记录，供 domain-modeling 后续处理。

## 决策冲突

方案与已有 ADR 冲突时，明确指出对应 ADR 和重新讨论的理由。
