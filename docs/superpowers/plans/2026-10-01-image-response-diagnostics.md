# Image Response Diagnostics Implementation Plan

## Goal And Scope

按[diagnostic contract](../specs/2026-10-01-image-response-diagnostics.md)定位真实MiniMax图片返回的身份拒绝，不改变拒绝行为。Parent为唯一writer；当前router树clean，不建worktree；Jianji已有外来改动保留。

## Owners And Milestones

1. **Reproduce / Implement:** 修改 `src/agent_subagent_router/minimax_image_wire.py`：原validator在具体拒绝处提供固定detail；修改 `transport/codex_broker.py`：secret先检查，唯一静态allowlist投影到失败observation与隔离摘要。新增负例至现有 `tests/unit/test_minimax_image_wire.py`、`test_minimax_image_broker.py`；真实body、headers和任意exception detail不可进入receipt。原error code、校验顺序、backend、model、TLS、credential、publication与no-replay不变。
2. **Verify / Install:** red-green focused，full offline、显式native Docker/fake、Ruff/diff；stable snapshot评估base §9 Risk Gate，符合实际trigger才增加required独立review。仅specific paths提交，官方installer管理entry/package，核对clean commit/program/Skill/config/Docker pins。历史package/receipts/host ledger保留。
3. **Diagnose / Resume Acceptance:** 新sealed probe绑定本Spec/Plan及原accepted refs，installed conformance成立后显式一次MiniMax图片诊断；新静态标签必须由canonical receipt观测，原失败未存body的原因继续UNKNOWN。只修复已确定且原合同允许的缺陷。GPT目录调查由原生只读mapper单独核查，无秘密/网络/写入。路线身份和项目执行owner未满足时，不发真实项目/盲审请求；正式holdout/source authority/productactivation不由此自动放行。

## Acceptance And Self-Review

交付必须有固定标签的可执行负例、秘密优先与任意detail拒绝证据、当前snapshot验证/安装、真实诊断receipt或真实blocker。工程diagnostic通过不能标视觉QUALIFIED，未评估指标仍null/NOT_EVALUATED。计划覆盖唯一owner、兼容、权限、未知结果不重试、清理与安装；完成后继续原完整验收，遇到已证明外部阻断才停止。
