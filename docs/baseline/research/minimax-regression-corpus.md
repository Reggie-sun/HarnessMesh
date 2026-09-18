# MiniMax Regression Corpus Design

Date: 2026-09-19
Status: source inventory and expected outcomes; fixtures and new router replay NOT IMPLEMENTED.

## Evidence Boundary

这是 global router 的 regression input catalog，AI-VIDEO 不拥有 router architecture。历史 diagnostics 是 advisory evidence；本轮没有重跑 MiniMax，也没有将旧 `model` 字段当作 observed provider identity。

现有 runner source：`/home/reggie/.codex/skill-repos/Reggie-skill/sub-agents/`。重点已读 `_builder.py`, `_dialogue.py`, `_executor.py`, `_stream.py`, `_evidence.py`、相应 tests 与两个 diagnostics reference。Native parent 保留 architecture conclusion 的复核责任。

## Cases

| ID | Source / observed signature | Expected new-system behavior |
| --- | --- | --- |
| MM-01 | `_dialogue.py:332-354`：`DONE_WITH_CONCERNS` 同时有非空 questions，旧协议拒绝；`01a03188…` 与 `01a02ed6…` rollout 可定位 questions constraint 报错 | legacy importer 保留 `PROTOCOL_CONTRADICTION`；不得清空 questions、改为 DONE/PASS；raw findings 仅供 parent 查看 |
| MM-02 | `01a02ed6…-fa606f042f7c6f1d.md` terminal table #3/#8：CLI=0，transport=1，`dialogue_protocol_error` / `PROTOCOL_ERROR` | 分离实际 process exit 与 parse/contract status；CLI 0 不代表有效结果 |
| MM-03 | `error_max_structured_output_retries` 在下述两份 rollout 的 tool outputs 中有定位 | `STRUCTURED_OUTPUT_EXHAUSTED`；保留 attempt budget/evidence，不自动再跑模型或降低 schema |
| MM-04 | `references/minimax-explorer-evidence-diagnostics.md`：explorer 宣称 service 可原样复用，parent 读 schema/writer/validator 后反驳 | mandatory concrete-file evidence floor + claim refs；parent 对关键结论重新检查，coverage 完整也不自动 semantic PASS |
| MM-05 | `01a03188…-4b45025ca4f0e028.md`：`explorer_tool_mismatch` | 记录 attempted/denied tool；不授予 Bash/Write，不 nested delegate；fail closed 或保留受限 findings |
| MM-06 | `01a023e5…-b939e6221f6c8951.md`：`zero_terminal_evidence` | required evidence nonempty 时 `EVIDENCE_INCOMPLETE`；未观测路径为 unknown，不能将“没抓到事件”普遍解释成“没读文件” |
| MM-07 | explorer diagnostics + current `_stream.py`：read-heavy exploration；心跳不是 semantic progress | liveness、tool completion、evidence coverage 分字段；有界 idle/wall timeout，不把新 tool ID 当作有效进展 |
| MM-08 | `references/minimax-writer-session-diagnostics.md`：fresh retry 在 exact grant 不匹配后反复 BLOCKED | parent 先检查已产生 artifact，再明确新 attempt；请求 hash 相同只能标记 retry-shaped，不能无证据认定为 retry |
| MM-09 | `_dialogue.py:356-366` 与 `test_string_null_state_file_is_normalized_to_none` | 新协议不需要 state_file；legacy normalization 只在版本显式声明且不存在同名真实文件歧义时允许，否则保留错误；记录原值/hash/normalizer version |
| MM-10 | required evidence gate 清除无效的结构化成功输出 | 无效内容留在 quarantined artifact 以便审查；parent API 不能暴露为可采用结果；不销毁诊断 provenance |

## Exact Local Locators

Sanitized reports：

- `/home/reggie/.codex/session-diagnostics/minimax/01a03188-327c-7052-85ee-20cba5cfbc38-4b45025ca4f0e028.md`
- `/home/reggie/.codex/session-diagnostics/minimax/01a023e5-9e51-7490-88bd-5fae6cc08e22-b939e6221f6c8951.md`
- `/home/reggie/.codex/session-diagnostics/minimax/01a02ed6-36fe-7923-bc1e-4f1aa6bc6d3d-fa606f042f7c6f1d.md`

Raw rollout files仅作本机受限查证，不复制到 fixture/prompt/repo：

- `.../.codex/sessions/2026/08/24/rollout-2026-08-24T10-10-04-01a03188-327c-7052-85ee-20cba5cfbc38.jsonl`，line 50 包含 structured-output exhaustion marker，line 122 包含 questions constraint marker。
- `.../.codex/sessions/2026/08/23/rollout-2026-08-23T21-36-25-01a02ed6-36fe-7923-bc1e-4f1aa6bc6d3d.jsonl`，lines 39 / 943 包含 exhaustion marker，3326 / 4855 包含 questions constraint marker。
- `.../.codex/sessions/2026/08/19/rollout-2026-08-19T18-03-37-01a01979-f2da-7c00-80b2-65ee2aea9ade.jsonl`，由 explorer diagnostics 指向。
- `.../.codex/sessions/2026/08/19/rollout-2026-08-19T12-43-21-01a01854-ba4a-7483-a9ac-0ca4f7ae686f.jsonl`，由 writer diagnostics 指向。

前两份的 marker 是 source locator，**不是独立运行计数**。例如 line 50 的 enclosing tool output 本身已有 capture summary，不能把引用了旧事件的摘要当作新 invocation；M7 必须沿 call/session/invocation association 追到原 terminal 才能冻结 observed case。无法关联则标 `UNRESOLVED_PROVENANCE`，只能生成明确标为 synthetic 的 regression，不能报成历史实测。

本轮对 line 50 原始 record 的 SHA-256 为 `d57eaae1c97a8ddd3e42ce7f9abde169f8072d89483115ab5d8d85e61ee0a262`；line 122 为 `18e90d3895b9483dc33f484a816b9cfee45999f5e41bea298845b58200ee4d0b`。hash 仅绑定 record bytes，不证明业务或模型 identity。

## Current Runner Findings

1. `_builder.AgentInvocation` 已是有用的 immutable invocation seam；Claude-family 与 native CLI builders 分开，具备 explicit tools、exact grants、MCP disabling、no-session-persistence 等基础。
2. `_build_kimi_args` 已存在，使用 `.com` endpoint；本轮所查英文官方指南推荐 `.ai`，这不证明 `.com` 已失效。该builder只设置 credential/base URL，不像 `_build_minimax_args` 一样覆盖全部 model alias。不能把已有 Kimi 名称视为 K3 profile 已接通。
3. `_resolve_api_key` 会允许 generic `CLI_API_KEY` fallback。新 provider credential supplier 禁止该跨 provider 隐式来源。
4. `_executor.py` diagnostic `model` 来自 invocation/env，不是 upstream response identity。
5. `_dialogue._protocol_error` 将 protocol failure 反映到 `transport_exit_code=1`；新 receipt 必须保留 observed process facts，用另一字段记录 parse failure，避免同一名称同时表示 OS fact 和 aggregate verdict。
6. `_dialogue` 的 status/questions/concerns invariant 是明确的旧 contract。减少新协议字段可以降低生成负担，但不得回写、放宽或“修绿”旧 receipt。
7. 工具覆盖不等于正确 reasoning；`Read` 成功也不代表看完全部文件。新 observation 记录 hash、range、truncation 与 tool-result 成功状态；parent 选择 evidence floor，router 不推测遗漏的业务 owner。

## Fixture Admission

M7 每个 case 包含：case ID、historical/synthetic classification、原 invocation identity（若可关联）、source locator/hash、脱敏后的最小输入事件、expected transport/protocol/evidence classifications、parent verification requirement。脱敏规则版本和 fixture hash 一并封存。

不导入 credentials、完整 prompts、全量会话、用户媒体或账户数据。Secret canary tests 使用虚构 sentinel；raw host logs 不进入 Git。Dedup 基于 invocation/attempt identity，不基于 report file 数、行数、marker 次数或 RAG chunks。

## Verification So Far

现有 `test_dialogue.py` 28 tests PASS（Micromamba Python，见 inventory）。这是 parser baseline，未运行新的 corpus replay；所有新 expectation 等待 accepted implementation。历史错误结论的当前业务适用性不在本 global research 中重新定案。
