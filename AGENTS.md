# Agent Subagent Router

## Authority

遵守 `/home/reggie/AGENTS.md` 与 `/home/reggie/.codex/AGENTS.md`。本仓库是 global router 的唯一 source owner；项目 Harness 与 parent acceptance 保留原 owner。

## Contracts

Accepted baseline 位于 `docs/baseline/`；当前 implementation 与 qualification 状态由 `docs/implementation-status.md` 记录。Source snapshot、sealed route、有限预算、无 fallback、credential 隔离与 upstream identity 必须 fail closed。Worker 没有 KEEP、commit、push 或 nested delegation 权限。

## Verification

默认测试不得调用真实 Provider。`python -m pytest -q` 为 offline suite；native conformance 由显式 `--native-conformance` 开启，仅调用本地 fake upstream。Live 必须显式命令、credential reference、sealed budget，且受 qualification gate 限制。没有 OS containment qualification 不允许项目数据或工具准入。

## Completion

区分 implemented、offline verified、native conformance 与 live qualified。禁止将 exit 0 或 fake evidence 写成 live acceptance。只提交本任务 files，不 push，不建立 remote，不创建 worktree。仓库无专用 capture skill；持久实施证据记录在 `docs/records/`。
