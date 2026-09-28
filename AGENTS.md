# Agent Subagent Router

## Authority

遵守 `/home/reggie/AGENTS.md` 与 `/home/reggie/.codex/AGENTS.md`。本仓库是 global router 的唯一 source owner；项目 Harness 与 parent acceptance 保留原 owner。

## Contracts

Canonical architecture contract 位于 `docs/superpowers/specs/2026-09-23-harnessmesh-rare-review-design.md`，其 exact accepted bytes 由 `docs/records/architecture-spec-acceptance.md` 绑定。`docs/baseline/` 仅是历史设计输入；当前 implementation 与 qualification 状态由 `docs/implementation-status.md` 记录。Source snapshot、sealed route、有限预算、无 fallback、credential 隔离与 upstream identity 必须 fail closed。Worker 没有 KEEP、commit、push 或 nested delegation 权限。

## Verification

默认测试不得调用真实 Provider。`python -m pytest -q` 为 offline suite；native conformance 由显式 `--native-conformance` 开启，仅调用本地 fake upstream。Live 必须显式命令、credential reference、sealed budget，且受 qualification gate 限制。没有 OS containment qualification 不允许项目数据或工具准入。

## Implementation Review Gate

连续 Kimi 工程审查运行故障的原生接手按 `/home/reggie/.codex/SUBAGENTS.md` 与
[用户窄修订记录](docs/records/architecture-spec-acceptance.md#user-directed-engineering-review-fallback) 执行；
下述 Kimi 默认规则受该显式例外约束。Image/live qualification 的无 fallback 与隔离门不变。

Spec 由 `superpowers:brainstorming` Self-Review 与 User Review Gate 接受；Plan 仅在 `superpowers:writing-plans` Routing Gate 触发时创建并由其 Self-Review 接受。两者均不默认调用 Kimi 或额外 Codex reviewer。

Implementation 先通过 project-native tests/Harness，再由 Parent 在 stable checkpoint 按 canonical Spec §9 的 Risk Gate 判断。未触发时采用 normal Codex verification；触发时只增加一名通过 qualified HarnessMesh route 调用的 read-only Kimi adversarial reviewer，由 Codex Parent 调查、修复并裁决 findings。Kimi 不拥有 KEEP、REVERT、completion 或 acceptance，也不得修改 source、Spec、Plan、tests 或 Harness。Review package、targeted/full re-review、三轮默认上限与 escalation 完全由 canonical Spec §9 管理；本文件不复制 trigger catalog 或形成第二 owner。

## Completion

区分 implemented、offline verified、native conformance 与 live qualified。禁止将 reviewer verdict、`PARSED`、exit 0、tests PASS 或 fake evidence 写成 acceptance。未触发 Kimi review 时，project-native verification 与 normal Codex completion rules 必须满足；触发时还必须完成 canonical Spec §9 要求的 Kimi review、Parent evidence adjudication、confirmed-blocker 修复与适用 verification，且没有 unresolved blocker。只提交本任务 files，不 push，不建立 remote，不创建 worktree。仓库无专用 capture skill；持久实施证据记录在 `docs/records/`。
