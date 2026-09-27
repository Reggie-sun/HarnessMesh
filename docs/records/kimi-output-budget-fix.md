# Kimi Output Budget Repair

Date: 2026-09-27

## Evidence And Cause

用户要求检查近期 Jianji / AI-VIDEO session 中反复出现的 Kimi 截断，随后明确要求修复。9 月 26–27 日、可由 execution-view 关联这两个项目的 15 次 project invocation 中，11 次 `PROCESS_OUTPUT_LIMIT`，4 次 `PARSED`；后者不代表项目 acceptance。

Jianji 导出目录排查 `d497e6ef-9fba-479d-857e-50d8e92073c6` 使用 32,000 bytes，后续 `36b1fef8-ede9-4c25-a562-16c06222e1c6` 使用 1 MiB，均截断。成功的 `f8560d1f-0129-4592-88cd-f8df8142d7d8` 最终语义 JSON 为 13,381 bytes，但 stdout observed 为 1,024,372 bytes，其中 3,392 条 `thinking_tokens` 事件序列化后占 657,196 bytes，工具结果占 294,630 bytes。该 receipt 的已过滤 artifact 为 1,024,377 bytes，不能把 artifact 大小冒充 raw observed 大小。

`supervisor.supervise` 对 stdout + stderr 总 retained bytes 执行原始总限额，超限终止；不是对最终 report 或模型 tokens 计数。每次 Read 的源内容和 native evidence、逐增 thinking 进度都会占额度。`project_run` 对截断输出执行 quarantine，partial JSONL 还可能使 observed_reads 解析失败；空列表不能证明模型从未读取任何文件。没有修改旧 receipt 或将失败调用升级为审查通过。

## Change And Compatibility

源码 commit：`6ab88ca7a3c40d8376d571325a2de84ae4b5adfc`；tree：`eb3656e1a492f55f0aff87bdd4dd27c0b6efe49d`。

- `TaskContract.from_dict` 在 Kimi task 的 output_bytes 缺省时填入 8 MiB，并在 resolve/seal 前写入 canonical task。其他 budgets 仍显式必填；非法显式数值仍拒绝，Gemini 不继承此缺省值。
- Live `run_contract` 对低于 2 MiB 的 Kimi project budget 返回 `OUTPUT_BUDGET_TOO_SMALL`，在 containment/provider 执行及 contract consumption 前终止并保存 zero-request receipt。小预算 synthetic upstream 测试仍可验证真实超限路径；CLI 不暴露该 synthetic seam。Fixed-input smoke 不属于 project task，不改变其预算。
- `inspect` 显示 sealed budgets，显式小额度附 live-blocked warning。已有小预算 seal 仍可读取，但 live 执行需要 parent 明确封存新的任务；不原地抬高旧额度。
- 已安装 Skill、README 与两个 live task authoring scripts 改用该默认值，说明 raw stream 与 report/context 的区别。默认额度不是 token 预付，也不改变 profile/effort。

2 MiB 是基于已观察到多次 1 MiB 截断而设置的 live admission 下限，不是声称每个任务都必须实际输出 2 MiB，亦不保证所有任务在此额度内完成。通常使用 8 MiB；16 MiB 硬上限、wall/idle/request 限额、原始双流 accounting、完整事件证据、quarantine、strict report 和 fail-closed 语义不变。本次不引入 telemetry filter、宽松 parser、自动 retry 或 fallback。

## Verification

- RED：关键新回归 7 failed / 9 passed，失败原因分别为缺省 output_bytes 被拒绝及 live 小预算未提前拦截。
- GREEN：focused 43 passed；补充 CLI budget/warning 覆盖后，全量 offline 为 232 passed / 12 skipped。未运行项目业务/media tests；本次未改 Jianji 或 AI-VIDEO。
- 真实 pinned Claude 的本地 fake-upstream native/project conformance：5 passed / 0 skipped，覆盖 worker/deep route、timeout、隔离工具与 sealed Read/report/receipt 链。
- 真实历史 artifact 回放：32,000 bytes 时 `output_limit` / 无 terminal；8 MiB 时完整捕获 1,024,377 bytes / terminal present。回放无 Provider request，不冒充新的 live generation。
- `ruff check src tests scripts` 与 `git diff --check` 通过。

## Managed Installation And Live Check

以 clean source commit `6ab88ca7a3c40d8376d571325a2de84ae4b5adfc` 受管安装；`source_dirty_at_install=false`，package identity 为 `ba7e43a42a79b402877017a9c073e855e5be8de8141d638d0b05fdf93e70f91f`，installed Skill SHA-256 为 `36bbb86a398619240ce491726f2315602ebd023a8c9725b94b1c88391cd59862`。实际 entry integrity check / `--version` 通过，doctor 的 OS/native synthetic qualification 通过。

安装后的 32,000-byte 检查：invocation `4d563bcb-a5e9-4600-9b61-321f60f281b0`，`OUTPUT_BUDGET_TOO_SMALL`，`wire_requests=0`，`process=null`，CLI exit 2。原 seal 和额度保持不变。

安装后的默认预算 live task seal 为 `ee341615a1e7311afcaf0b5da4f3d9e9f2955db66a2c7b0264f89ffd3143057c`，实际 sealed output_bytes 为 8,388,608。Invocation `12752225-a883-4e8e-9f6b-dfb901939bef`：`PARSED`，2 wire requests，`k3-256k/high` 的 authenticated endpoint identity verified，3 个 source Read 经机械验证；stdout 314,640 bytes、stderr 74 bytes、report 4,403 bytes、72.09 seconds，无截断。`subagent receipt` 重读及 artifact hash 校验通过。

Parent 核对 Kimi 的三项 findings：前两项（默认值封存、小额度零请求拒绝）由当前源码及执行证据确认。第三项声称 fake-upstream 低预算分支缺测试，并明确承认未读取其他 test files；此全套覆盖缺失判断为 `FALSE_POSITIVE`：已运行的 `test_sealed_project_invocation_binds_native_read_report_and_receipt` 明确用 1,000,000-byte budget、non-None upstream 经完整 `run_contract` 返回 `PARSED`，会捕获该分支被错误移除的回归。其附带的非整数数值测试建议是非阻断覆盖建议；原 `Budgets` 的精确 integer 校验保持不变。无 unresolved blocker，不为模型达成一致追加调用。

## Parent Risk Decision

上述 commit/tree 是 stable implementation snapshot。`KIMI_REVIEW_NOT_REQUIRED`：用户要求修复，未额外要求 implementation adversarial review；本次限制过小预算的付费执行、补充封存前缺省值，未引入凭据/权限/写入/持久状态损坏路径。默认传输额度增大可能使原来过早中断的调用运行更久，但既有 wall/request/16 MiB 总上限仍在。预算边界、seal preservation、拒绝时零请求、实际 native 协议均已有可执行证据，不存在重大后果且需第二模型解决的剩余语义缺口。

Kimi test-investigator 用于安装后的受管只读验证，不冒充 required adversarial review；Parent 负责源代码核验、finding 裁决和完成决定。无新增 Spec/Plan、无 push/release。Codegraph/tool_search 当前未暴露，调用关系由源码与真实入口验证。
