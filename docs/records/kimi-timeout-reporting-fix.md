# Kimi Timeout And Reporting Repair

Date: 2026-09-27

## Incident And Root Cause

用户要求处理反复超时；触发 session 为 `01a0e229-b369-73c2-b7fd-1811f8f99477`。AI-VIDEO invocation `ab33aa6b-f491-4dfe-88de-05c4d2e77dd5` 在 1200.029 秒达到 wall deadline：stdout 4,874,673 bytes、未截断、15 次 wire requests，前 14 次 identity verified，第 15 次 `OUTCOME_UNKNOWN`，没有 terminal report。其 sealed package 包含 37 个文件、20 个 required evidence paths；实际 stream 有 32 次 Read、3 次 Grep。Receipt 的空 observed_reads 不代表没有工具读取，不能把未完成结果计作独立审查通过。

另外两个调用分别触发 idle：`999f2cc0-8c28-4d8a-b9e7-65e7a8c85b90` 为 idle 180 秒，`00972768-de84-4791-92c3-2d4cb3ad98d5` 为 idle 60 秒。源码中 `KimiUpstream` 在完整 `response.read(limit+1)` 返回前不通知 supervisor；即使上游持续传来数据，runtime stdout 仍可保持静默，导致误判 idle。Claude 自身的 first-byte/stream idle 也原先采用 idle budget，和完整验证后交付的 broker 策略冲突。

总时限超时和 idle 误判是不同问题。前者的持续探索没有明确收尾预算，不能仅通过消除 idle 误判解决。

## Change And Boundaries

Source commit：`4773dabaae3d74971d9ee84a4a152a7d5a78ff30`；tree：`d2b62e1f81464af27a986a7a275af702dabfe47b`。

- `KimiUpstream` 通过有界 `read1` 接收数据，实际 headers/chunks 更新 broker activity，supervisor 合并此可信 I/O 和 runtime stdout/stderr 判断 idle。不生成假 heartbeat，传输活动不证明语义进展；wall/cancel/output limit 保持有效。
- 完整 response 仍须通过原身份/终态校验后才交付 runtime，未改为不验证的边收边转发。Claude 自身等待上限采用 wall budget，实际 idle 由 supervisor 独占判断。
- 独立 `transport/budget.py` 在项目 wire 请求中附加剩余预算。收尾预留为 `min(wall / 2, max(30, wall / 4))` 秒；20 分钟任务预留 5 分钟。剩余时间进入预留区，或只剩本次请求时，进入 `FINAL_REPORT`，移除 tools/tool_choice，要求按原 schema 报告缺失证据。上游此时仍要求工具则拒绝交付。
- 保留原 user/tool-result 内容及 model/thinking/effort。Receipt 的 `request_sha256` 对应实际 wire bytes，另记 client request hash、budget phase、wire duration、收到的 upstream bytes；不保存秘密或额外原始请求正文。
- 项目 readonly/writer 共用该预算规则，smoke 只获得真实 I/O activity。Worker 仍无 host apply/acceptance 权限。未放宽 required Read、strict report、route identity、containment 或 Parent acceptance。

没有增加 timeout、请求额度或自动 retry，没有 fallback，没有修改 AI-VIDEO/Jianji、accepted Spec 或历史 receipt。Scope 只涉及 HarnessMesh transport/activity/reporting owner。

## Verification

- RED：新 activity/budget 接口与 CLI 等待预算测试先失败；追加 FINAL_REPORT tool refusal 和 malformed messages 测试再次失败，修复后通过。
- 全量 offline：246 passed / 15 skipped。`ruff check src tests scripts`、`git diff --check` 通过。
- 真实 pinned Claude + 本地 fake upstream/containment：12 项 native tests 通过，覆盖 readonly/writer projection、route/report/receipt，以及持续分块超过 idle、真正停滞、错误模型身份。Fake upstream 不是 live qualification。
- 回归明确验证实际数据刷新 idle 但不延长 wall，response hard limit 保持，收尾时 SSE/非 SSE 工具调用均拒绝，转换后请求不超原上限，输入 evidence 不变，错误 identity 不交付。

## Managed Installation

Clean source 安装绑定上述 commit；`source_dirty_at_install=false`，package identity：`ea40ff7b2239dd708b055476f06110e51ef65bda478348ad1b1f3a1f8661903d`。Installed Skill SHA-256：`1ef685f7f7c46cd2b60b4d5fb970c09c953e4ec66df2a69d6a6707aa85a5eb6f`。CLI integrity/version 与 doctor 的 OS/native synthetic containment 检查通过。保留旧安装与历史 receipts。

## Live Check And Parent Adjudication

仅一次受管 `test-investigator` 调用，`worker / k3-256k / high`；scope 为 `transport/budget.py` 与 `tests/contract/test_budget_reporting.py`，两者必须实际读取，无写入/测试执行/nested delegation 权限。Seal：`23dc2ddbc4e84cb5dd28a650f02fba7dcca4ebb05161d1a7af1e5eed2a093b32`；budget：wall 180 秒、idle 60 秒、2 requests、默认 8 MiB。

Invocation `7accbc36-8d8e-42a9-bd65-efce20419a9c`：72.625 秒退出，`PARSED`，stdout 56,383 bytes、stderr 74 bytes，未截断。两次 wire phase 分别为 `EXPLORE`、`FINAL_REPORT`，均为 authenticated endpoint identity verified，分别收到 10,413 / 109,492 upstream bytes。两个完整 Read 均与 sealed source hash 匹配，最终 report 2,768 bytes；receipt 重读校验成功。无 Parent 自动重试，`internal_retry_count=unknown` 保留原真值，不将它伪造为零。实际费用未提供。

Kimi 三项描述性 findings 分别为 reserve 公式、final tools 移除和输入不被修改；Parent 对照上述 source/test bytes 核实为 `CONFIRMED`，均非 blocker。它明确未执行 tests、未读取 scope 外 Broker internals；这些限制由 Parent 的 246 offline / 12 native 执行证据与 broker diff inspection 补足，不扩大 Kimi 检查范围。没有 unresolved finding，也未为了争取共识追加调用。

本次验证证明小范围任务可经新 installed route 正常收尾；不能证明所有大规模 deep review 的完成率，亦不能把 `PARSED` 本身当成 acceptance。

## Parent Risk Decision

Stable snapshot 为上述 commit/tree。按 accepted Spec §9，`KIMI_REVIEW_NOT_REQUIRED`：

1. 用户要求修复超时，没有额外要求该 implementation snapshot 的独立 adversarial review。
2. 变更未扩大权限、凭据传播或 host 写入；完整身份校验后交付仍在，并新增收尾工具拒绝测试。没有发现关键级凭据泄露、越权或难恢复 durable-state 损坏路径。
3. 剩余后果主要是有限额度内的可用性/付费浪费或未完成报告；真实 CLI 的慢流、停滞、错误身份及 readonly/writer 路径已有执行证据。没有同时满足重大后果、残留实质验证缺口和额外 adversarial reviewer 增益三项条件。

受管 Kimi test-investigator 是 narrow helper/test 检查兼安装后 live 验证，不冒充 required adversarial review。Parent 保留源代码核验与 findings 裁决。

## Limitations

收尾阶段只在新的 wire request 准入时计算，无法打断已运行的长生成并强迫它交出答案。上游完全停滞、单次生成超过总时限、证据包过大或 report 不合规仍会失败；8 MiB 默认输出额度也不保证所有任务完成。不能承诺消除所有 Kimi 超时或扩大现有 qualification 到 provider-wide reliability / 1M consumption。

没有新 Spec/Plan、push/release。Accepted Spec SHA 保持 `a3c216c077608767e1ac7ac7d03869e8d90f49256469691e8206c71edbf3566c`。Codegraph/tool_search 未暴露，以源码调用关系与真实入口验证补足。仓库无 capture skill，本 record 为持久 owner。
