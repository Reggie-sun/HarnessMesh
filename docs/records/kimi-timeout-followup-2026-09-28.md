# Kimi Timeout Follow-up

## Status And Scope

2026-09-28 用户同意继续处理新超时及 `SOURCE_CHANGED`，随后明确选择“增加显式生成上限，截断就失败，不自动重试”。本 checkpoint 完成 source drift 的提前拒绝、parent 操作约束及显式生成上限；不保证所有任务成功完成，不把下面的测试或小调用当成整体可靠性证明。

## Current Evidence

- Jianji `7de3fb0d-b9f8-49c5-b443-4c462917d39c` 使用前次修复版本 `c97a9d64e17fe1791dadeb618b550c164f128033cec1b389c59e031529997673`，wall 180 秒耗尽。第二次请求处于 EXPLORE，持续约 166.54 秒，已接收 688,562 bytes；最终 OUTCOME_UNKNOWN。不是 output truncation 或旧 idle 误判。
- `730d9dd0-c303-4f33-8209-7811bfaf9375` 和 `7a007c6f-2439-41a9-985f-4eb6899bdc7a` 正常退出后因 SOURCE_CHANGED 拒收，分别约 106.39 / 190.19 秒。必须与 timeout 区分。
- 真实 pinned Claude 2.1.277 对本地 fake upstream 的只读 wire 探针：worker 为 k3-256k/high，deep 为 k3/max；两者均发送 `thinking.type=adaptive` 和 `max_tokens=32000`。没有联网生成，探针退出均为 0。前次 `MAX_THINKING_TOKENS=8192` 不能被描述为这个 adaptive 请求的硬 thinking 上限。

`reporting_request` 只在准入新请求时计算 phase。单次请求已经在执行时不会获得新的 FINAL_REPORT 提示，不能强迫远端提前交出终态。 [Claude extended-thinking 文档](https://platform.claude.com/docs/en/build-with-claude/extended-thinking) 明确 max_tokens 包含 thinking；[Kimi 配置文档](https://www.kimi.com/code/docs/en/kimi-code-cli/configuration/config-files.html) 也区分输出 token cap 与 context size。因此直接压小输出可能变成截断，并不保证时限内得到完整可验证报告。

## Source Stability Repair

Owner 保持 resolver.verify，不新增第二套快照验证。Broker 在每次 project paid request 前调用原完整 validator；readonly 和 scoped writer 均接入，smoke 不受影响。失败则记录 typed rejection、撤销 capability，且不增加 Provider 请求数；host 恢复旧 bytes 不能静默复活已撤销 invocation。Guard 不在 broker lock 内执行，以免 filesystem validation 阻止 supervisor 的 wall/cancel revoke。

结束时的原验证仍保留。这里没有文件锁，不阻止别的 session 写入，也不能收回已发送的请求；后续请求的 guard 和最终校验共同保持 fail closed，不把 drift report 自动当成当前源码有效证据。

`inspect` 新增 `frozen_source_paths`，列出完整 host source 集合。Canonical external-subagent Skill 要求 Parent 在 seal 至 receipt 核验期间保持整个集合不变，包括适用 instructions、Spec/Plan、Harness 和 Skill assets，其他并行工作只使用集合外文件。同文件 active writer 冲突须先解决，再 seal，不用新 worktree 或复制整个 repo 绕过。

## Verification

RED：修正测试 import 后，4 项测试因缺失 before_request guard 和 frozen_source_paths 字段失败。GREEN：focused 20 passed，全量 offline 247 passed / 17 skipped；ruff 与 diff whitespace 检查通过。

真实 Claude + local fake upstream 的 project conformance 覆盖 unchanged success、第一次响应期间 host 改动后下一请求零送出、最终响应期间 host 改动后仍拒收；unit/contract 用真实 resolver seal 与 host 改写验证不可复活。没有调用 Jianji/AI-VIDEO 业务 tests，未修改业务仓库。

## Managed Kimi Investigation

使用 external-subagent standing route，role=test-investigator，worker/high，仅核对 budget helper 及其测试，两个源文件和适用规则在调用期间保持不变。不是 implementation adversarial review。Invocation `9576738c-3d3a-4a0d-a3a5-7c6427bffdf3`，seal `f199a069ca34f311d225f8aa5f271ca983b45bd2c523da7dd32f75ec9affc3b4`，wall 180 / idle 60 / 2 requests / 默认 8 MiB；79.21 秒退出，两次 identity verified，两个 Read 完整可核验，但 terminal result 用 Markdown code fence 包裹 JSON，严格 parser 返回 PROTOCOL_ERROR。没有可接受的 worker report，不采用它的结果、不自动重试、不放宽 parser。

Doctor 初次返回 SANDBOX_DOCKER_UNAVAILABLE；随后只读 docker info 成功，重新进行零 Provider 请求 doctor 后 containment 通过。未重启 daemon、改权限或换隔离机制。

## Parent Risk Decision

本 checkpoint 的变更是 source-stability admission guard、inspect 的 frozen-set 显示和操作说明。KIMI_REVIEW_NOT_REQUIRED：用户未额外请求 snapshot adversarial review；没有扩大凭据、权限、网络、host 写入或 acceptance；原 validator 复用且终态拒收保留，未发现关键级泄露/越权/难恢复状态损坏路径。错误拒绝的代价是有限调用失败，guard wiring 与最后一次响应 drift 均有 native proof，不同时满足重大后果、残留实质验证缺口和独立 reviewer 增益条件。Kimi 调查失败不被计作 review 通过；这里不依赖其结论。

## Explicit Generation Budget

用户明确选择有限生成，未选择延长所有调用或降低 reasoning。新 Kimi project seal 的 `budgets.generation_tokens` 缺省为 4096，允许 Parent 显式选择 1024–32000 的整数。默认值是可检查、可显式调整的成本上限，不是基于未测量 tokens/s 推算的 SLA。thinking 与 report 共用此额度。Inspect 阶段 materialize 默认值；legacy manifest 缺失字段保持原 bytes，live run 在任何请求前返回 GENERATION_BUDGET_REQUIRED。Gemini 不注入此缺省值。

Claude project runtime 设置输出 token cap；broker 对实际请求再次执行 min(client max_tokens, sealed cap)，不增加客户端额度、不修改 model/effort/thinking。Manual thinking 与较小 cap 不兼容时拒绝，不切换 adaptive 或降低 thinking。Receipt 记录实际 request_max_tokens、sealed generation_token_limit 和转换前后 request hashes。

完整上游 response 的 stop_reason 为 max_tokens 时，即便已经有一段看似完整的 JSON，也返回 UPSTREAM_GENERATION_LIMIT、拒绝交付并 revoke，阻止 runtime continuation 或额外付费请求。报告的 output_tokens 超过实际请求 cap 同样拒绝。身份、证据、strict report、wall/idle 和 Parent acceptance 仍适用。不能防止服务端在 token 耗尽前停滞；也不能承诺降低失败率，结果可能从超时变成明确的生成上限失败。

Token 变更的 RED 为 8 failed / 6 passed（新增接口尚不存在）；补齐 adaptive fixture 后 focused 19 passed。未将 legacy 8192-token manual-thinking fixture 强制降档来让测试通过，另保留 incompatible-budget 拒绝测试。

该用户批准的预算限制追加到本 checkpoint 的 Risk Gate：它只缩小新 task 的已封存付费输出额度，并对截断 fail closed，没有扩大权限或改变模型身份。Native wire proof 检查 worker/high 和 deep/max 保持；不因 public budget field 存在机械触发额外 review。结论仍为 KIMI_REVIEW_NOT_REQUIRED；Parent 承担裁决，不依赖上述失败的 Kimi 调查。

## Final Verification

Stable implementation snapshot：commit `1d8b134d181d7ae8e398ad5614196b82290a3113` / tree `c0e4cae13dd190551d8e602f317cbe15c443d5e9`。本 record 后续仅补充执行证据，不改变该代码身份。

合并全部变更后 offline 为 **268 passed / 20 skipped**，ruff / diff whitespace 通过。真实 Claude + local fake upstream / containment 为 **17 passed**，新增覆盖 worker/deep wire cap、SOURCE_CHANGED 零后续请求、终态期间 drift 仍拒收，以及看似完整 report 被 max_tokens 截断时拒绝并不续写。Gemini 若显式携带此未实现的生成 cap 会被拒绝，不能静默忽略。

测试过程中曾因 guard 内错误地再次获取同一非重入锁而阻塞定向 test process；定位后修正为现有 lock 内的有界 rejection append，并仅终止该测试 PID。随后 manual-thinking 不兼容与 invalid max_tokens 测试均通过，未放宽 contracts。

## Managed Installation

以 clean source commit `1d8b134d181d7ae8e398ad5614196b82290a3113` 安装，source_dirty_at_install=false；package identity `90b5403a5525bde812c9aa4082c7e770f35d909f3f7891c7162d6a318c3fa831`，Skill SHA-256 `a82abac901b7c60b3a49b0d192d8950d49cd99984beb407fe7bde5e116af5ede`。CLI integrity/version check 通过，inspect 显示 generation_tokens=4096 与完整 frozen paths。保留旧 installation 与 receipts；新 invocation 用新安装，已经启动的其他 invocation 不被中断或重写。

## Installed Live Evidence

安装后仅一次新 cap 验证，不重试先前 budget-hint 调查或业务 review。只读两文件 contracts.py / test_generation_budget.py；seal `820fa032d5311d66a4bce5409df5d0ccf4ff775f52c05fad8dd194d6480fff94`，显式 generation_tokens=4096、wall=180、idle=60、request_limit=2。整个 frozen set（含两个 AGENTS.md）在运行期间保持不变。

Invocation `f91a3e03-bda5-4281-b833-5d2025d15150`：33.899 秒正常退出，PARSED，未截断，2 次 wire 均为 k3-256k/high、adaptive、authenticated endpoint identity verified；两次 request_max_tokens / generation_token_limit 均为 4096，output_tokens 分别 92 / 708。阶段为 EXPLORE → FINAL_REPORT，两个完整 Read 的 path/hash/range 已校验，receipt 重读及 artifacts 校验通过。实际费用未提供，internal_retry_count=unknown 保持原真值；orchestration_retries=0。

Parent 对两项描述性 findings（typed token budget 范围、legacy seal 的测试预期）逐一核对源码和已执行 tests，均为 CONFIRMED、非 blocker。Kimi 明确只做 inspection、没有执行 tests，也未审 api.py 实现；这些部分由 Parent 的 source review 和可执行测试负责，不扩大它的检查范围。没有 unresolved finding，不为达成共识加一轮。

最终 source snapshot 再跑 **17 native tests passed**。本次 authenticated live proof 仅覆盖 worker；deep/max 的新 cap 由 pinned CLI + fake upstream 验证，未新增 deep live cap benchmark。33.9 秒不是与旧失败任务同负载的 A/B，不能据此计算速度提升或声称大任务可靠性已解决。达到输出上限的拒收/禁止续写路径由 native synthetic 回归证明，没有故意付费制造 token exhaustion。

没有新 Spec/Plan、push/release；accepted architecture bytes 未修改。Codegraph/tool_search 不可见，依据 current source 与 executable boundary tests 检查。仓库没有 capture skill，此 record 为持久 owner。
