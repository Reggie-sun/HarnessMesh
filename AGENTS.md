# Agent Subagent Router

## Authority

遵守 `/home/reggie/AGENTS.md` 与 `/home/reggie/.codex/AGENTS.md`。本仓库是 global router 的唯一 source owner；项目 Harness 与 parent acceptance 保留原 owner。

## Contracts

Accepted baseline 位于 `docs/baseline/`；当前 implementation 与 qualification 状态由 `docs/implementation-status.md` 记录。Source snapshot、sealed route、有限预算、无 fallback、credential 隔离与 upstream identity 必须 fail closed。Worker 没有 KEEP、commit、push 或 nested delegation 权限。

## Verification

默认测试不得调用真实 Provider。`python -m pytest -q` 为 offline suite；native conformance 由显式 `--native-conformance` 开启，仅调用本地 fake upstream。Live 必须显式命令、credential reference、sealed budget，且受 qualification gate 限制。没有 OS containment qualification 不允许项目数据或工具准入。

## Final Review

本repo的control-plane、security、permissions、qualification或public contract change，final parent在runtime可选时使用Astra / Extra High；native reviewer MUST 使用read-only `reviewer_xhigh`，Kimi reviewer MUST 使用read-only `deep` / max，只有sealed evidence确需时才使用1M上下文。两侧必须审查同一immutable `review_snapshot_id`且互不读取review结果。Codex重点检查architecture、correctness、regression、spec一致性与Harness；Kimi重点检查adversarial paths、edge cases、authority violations、evidence gaps、unsupported assumptions与failure paths。两侧都可报告任何blocking candidate。

Reviewer只产生findings，不拥有acceptance truth，并且MUST NOT修改代码、派生subagent、自行降低blocker severity或因另一reviewer PASS而改变结论。Parent依据 `/home/reggie/.codex/SUBAGENTS.md` 的adjudication state machine关闭findings；任何修复或review input变化产生新snapshot并重跑两侧。

## Completion

区分 implemented、offline verified、native conformance 与 live qualified。禁止将 reviewer verdict、`PARSED`、exit 0 或 fake evidence 写成 acceptance。只有同一immutable snapshot上的两侧review完成、parent adjudication达到`unresolved_blocking_findings == 0`且project Harness通过，才具备completion eligibility。只提交本任务 files，不 push，不建立 remote，不创建 worktree。仓库无专用 capture skill；持久实施证据记录在 `docs/records/`。
