# Scope And Authorization

用户本轮“可以”批准对 Jianji 九文件分组候选追加最多 **3 个 paid Kimi invocations 总计**，分别针对 admission/fence、group ready/ownership、unknown/recovery/resume；保留 `deep / k3[1m] / max`。这是 exhausted review budget 的显式一次覆盖，不是自动第四轮、不按 scope 重置三轮、不改变 canonical review governance。

本轮没有修改 router/Jianji runtime、Spec、Plan、安装、账号配置或广告设置；没有浏览器、上传、确认、发布或 release 操作。

# Current Snapshot And Package

Jianji HEAD：`9f4dd46f6a7b223c5722a5a6b39e2dd9245e4281`。自原审查候选以来，`7855891` 已添加 `runPending` 的 active guard 及 resume/自动上传互斥回归；不能声称旧 snapshot 覆盖新 bytes。

准备材料在 `/home/reggie/vscode_folder/jianji/.agent/harness/runs/20260929-qianchuan-scoped-review/`：

- `snapshot.json`：18 项 source/instruction/test/accepted-ref hashes、changed paths、HEAD、diff base、working-tree identity、授权预算及 route 阻断状态。Exact bytes SHA-256：`da40762a34c9e90c67ca8ff1135fff7e06cdd7848985e661cc73fec3a5491cc1`。
- `review-context.md`：用户批准的九文件增量、verification/evidence 边界、coverage 合并和 stop conditions。
- `01-admission-fence.task.json`、`02-group-ready.task.json`、`03-unknown-recovery.task.json` 及各自 source-only diff。

材料状态：`PREPARED_NOT_SEALED_NOT_REVIEWED`。这是可检查的 package，不是 successful HarnessMesh seal 或 live eligible final candidate。每份 task 均已通过 canonical `TaskContract` 的本地 schema 校验、accepted-ref/hash/路径检查；最新 package 的各份 input bytes 均经机械检查低于 350000 context budget。Source hashes 已机械核对。Diff 不含完整 test diff，exact current test files 由 manifest/Read scope 提供；不发送无关工作树内容或用户数据。

每次 task 的 finite budgets：wall 480s、idle 240s、requests 2、generation 8192（含 thinking）、context 350000 bytes、output 8 MiB。第一请求 batch 必要 Read，最后请求 FINAL_REPORT。截断即失败、无自动 retry；scope 缩小不构成必然按时生成的保证。

# Preflight Blocker

当前安装：source commit `679f985d2ce2df4ffdb0a5249979c4f92635f91a`，source hash `142bc8650c9c5c285cf7b12ffcf90730b29732b71a423b0271f2b28a4968ba13`。

`subagent doctor --backend kimi` 返回 `BLOCKED_CAPABILITY` / `SANDBOX_IMAGE_UNAVAILABLE`。实际 sandbox 配置存在、指定 pinned image；`docker version` 的 Server 为 null，并报告连接 `unix:///var/run/docker.sock` permission denied。因此该分类不能证明 image 不存在或 Kimi 服务故障。

实际执行一次 canonical `subagent inspect`（scope 01）同样零请求返回 `SANDBOX_IMAGE_UNAVAILABLE`，没有产生 seal。没有运行 `subagent run`；追加 paid invocations **0/3**、Provider requests **0**、有效 Kimi reports **0**。没有新 invocation receipt，不能编造 reviewer identity 或 findings，也不绕过 Docker、换模型/profile、使用 direct API 或增加系统权限。

# Fresh Verification And Limits

本轮 `npm run typecheck` exit 0；四个相关离线测试文件 49/49 PASS、无 skip：

```text
npm test -- tests/douyin-upload-service.test.ts tests/douyin-upload-store.test.ts tests/qianchuan-page-contract.test.ts tests/douyin-upload-integration.test.ts
```

没有重跑 CDP/browser、完整 code Harness、FFmpeg、packaged application、真实账号或 Windows；既有记录仍保留原运行快照。Jianji 的无关未提交制作/UI 文件和用户项目删除保持原状。仅增加 ignored Harness run artifacts，不修改 AOCI 正式受管理对象或接管其他任务的索引。

按 current AOCI CLI 执行 Verify、Check，均 exit 0；`index agent guide --agent codex` 返回 `complete:true / stage:aligned / next_action:none`，无需写正式 Entries/Baseline。未将该索引对齐结论当作行为验收或 Kimi review 完成。

# Handoff And Gate

在能访问原本受管 local Docker route 的普通终端，先运行 `subagent doctor --backend kimi`，不要改 socket 权限、提升 runtime 权限或绕过 qualification。只有 containment preflight 合格后，Parent 才补齐 applicable fresh native verification、复核整个 common source hash set、更新 evidence/manifest 并对 task 重新执行 canonical inspect。新的 manifest SHA 和 seal 需如实记录；此处 hash 不代表之后的更新版本。

付费调用使用当前 matching deep qualification 和 runtime-side credential reference；不将 credential 内容复制进 package。封存至每次 receipt 核验结束不得修改整个审查 union 的 source/ref/instruction bytes。每次调用后 Parent 先调查 receipt/identity/actual Reads/findings；不自动执行三个 task。Semantic fix 需新 snapshot、verification 与适用 re-review，不能把 S1 的结果直接覆盖 S2。

Parent 必须检查三个 scope 的联合覆盖，并 evidence-adjudicate 每个 blocker。任何 failed/missing review 或 acceptance-relevant uncertainty 继续阻断。当前 `REVIEW_ESCALATION_REQUIRED` 保留；本轮只完成 package preparation 和 blocker evidence，不宣称 required review 完成或 timeout 已修复。

仓库无专用 session-record/capture skill；本文件是实际 preflight/verification/handoff record，不写全局 memory。
