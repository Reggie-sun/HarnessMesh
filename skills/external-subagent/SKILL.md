---
name: external-subagent
description: Route standing-authorized Kimi or an explicitly selected external backend through sealed project contracts and supervisor receipts. Never replaces parent project acceptance.
---

# External Subagent

## Authority

遵守当前平台、用户、global/project rules。当前用户已在 `/home/reggie` workspace授予Kimi standing authorization；global `AGENTS.md`命中non-trivial route或用户明确点名Kimi时必须使用本Skill。此Skill是`subagent` CLI的薄入口，不自动重试、不扩大scope，无nested delegation或worker acceptance。默认选择`worker`；跨模块、长上下文、architecture/security/high-risk或用户要求最强模型时选择`deep`。

## Invocation

1. `subagent doctor --backend <selected-backend>`检查sealed contract所选backend的OS/native containment；它只使用fake upstream，不证明live account/identity。
2. Parent 编写 task JSON：显式 backend/profile、role、cwd、read/write paths、exact accepted refs、required evidence 与 finite budgets。没有 active docs 明确 `not_applicable`；Skill 重名用 exact path；dirty target 按用户 ownership 规则处理。
3. `subagent inspect --cwd <repo> --task <task.json>` 封存 inputs/route/runtime/image，不联网、不执行项目 scripts。
4. `subagent run --contract <manifest.json> --backend kimi --profile <selected-profile> --live --credential-ref <private-reference.json> --qualification <matching-canonical-route-id>`；`<selected-profile>`必须与sealed contract一致，且`worker`/`deep`使用各自matching qualification。Gemini用`--backend gemini --profile worker`，不传Kimi qualification；使用已有private OAuth reference，账号不合格即阻断，不登录/onboarding。
5. `subagent receipt <invocation-id>` 检查 process、protocol、upstream identity、artifacts 和实际 Read evidence。`PARSED` 不等于 KEEP；native independent review 和项目 Harness 由 parent 负责。

## Dual Review

Non-trivial final review时，Kimi使用`reviewer` role、read-only permissions与`deep` profile，读取与Codex native reviewer完全相同的immutable `review_snapshot_id`、commit/tree、exact staged diff、accepted spec/plan、Harness定义和verification evidence。Kimi prompt与snapshot不得包含Codex review、peer findings、comparison record或parent adjudication。

Kimi只在canonical五字段report的`findings`中输出findings；每项包含stable ID、`blocking_candidate`或`non_blocking` severity、trigger、impact、snapshot evidence与建议验证。不得输出拥有acceptance语义的verdict，不得修改代码、派生subagent、自行降低severity或因peer PASS改变结论。`PARSED`只证明报告协议有效。Parent将findings纳入adjudication ledger；任何修复或review input变化都会产生新snapshot并重跑Codex与Kimi两侧。

## Writer

Kimi implementer 只支持一个干净、已跟踪的 owned target，权限 `read,candidate-write`，另传 `--readonly-qualification <canonical-M7-id>`。Worker 仅写 private candidate，不写 host project，不执行测试。

Parent 用 `candidate-test --invocation <id> --argv-json <exact-argv.json>` 在无 broker/key/network 的隔离域测试 sealed candidate，再用 `candidate-apply --invocation <id> --test <test-id>`。Apply 检查 preimage/ownership/hashes，保留 displaced inode/recovery；conflict/unknown 不自动回滚或重试。Parent 核验最终 bytes 并执行项目原生 gates 后作 acceptance。

## Evidence And Limits

Kimi worker/deep 本机 live route 与两 repo holdout 已有 canonical qualification；deep 实际 1M consumption 未评估。Gemini native/fake 已通过，现有 Code Assist account 返回 `UNSUPPORTED_CLIENT`，两 repo live 仍 blocked。不能把 fake receipts、CLI init、exit 0 或模型自述当成 authenticated identity。

真实 credential 只经 private provider-specific file reference 注入，不进入聊天、argv、prompt 或日志。没有 fallback 到旧 `sub-agents`/MiniMax runner。Follow-up 必须由 parent 检查旧 outcome/artifacts，并新建有理由、独立有限预算的 attempt；禁止删除 budget/consumed records。无自动 accept、revert、commit 或 push。
