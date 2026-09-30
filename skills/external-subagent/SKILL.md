---
name: external-subagent
description: Route standing-authorized Kimi or an explicitly selected external backend through sealed project contracts and supervisor receipts. Never replaces parent project acceptance.
---

# External Subagent

## Authority

遵守当前平台、用户、global/project rules。当前用户已在 `/home/reggie` workspace授予Kimi standing authorization；global `AGENTS.md`命中non-trivial route或用户明确点名Kimi时必须使用本Skill。此Skill是`subagent` CLI的薄入口，不自动重试、不扩大scope，无nested delegation或worker acceptance。按用户选择的 global maximum policy，新 Kimi project task 选择 `deep` / max / 1M；`worker` 仅保留用于已有 seal/资格，不在 run 时升级。

## Invocation

1. `subagent doctor --backend <selected-backend>`检查sealed contract所选backend的OS/native containment；它只使用fake upstream，不证明live account/identity。
2. Parent 编写 task JSON：显式 backend/profile、role、cwd、read/write paths、exact accepted refs、required evidence 与 finite budgets。没有 active docs 明确 `not_applicable`；Skill 重名用 exact path；dirty target 按用户 ownership 规则处理。
3. `subagent inspect --cwd <repo> --task <task.json>` 在新 Kimi seal 前执行下述 maximum policy，再封存 inputs/route/runtime/image，不联网、不执行项目 scripts。核对输出的 `route.profile`、`budgets`、`resource_policy` 与 `frozen_source_paths`；没有 `resource_policy` 的旧安装不能被视为已启用该策略。
4. `subagent run --contract <manifest.json> --backend kimi --profile <selected-profile> --live --credential-ref <private-reference.json> --qualification <matching-canonical-route-id>`；`<selected-profile>`以 inspect 的有效 sealed route 为准，新 seal 使用 `deep` 及其 matching qualification，不能照抄原 task 的 `worker` 或使用 worker qualification。旧 seal 仍使用自己的原 profile/资格，不在 run 时改写。Gemini用`--backend gemini --profile worker`，不传Kimi qualification；使用已有private OAuth reference，账号不合格即阻断，不登录/onboarding。
5. `subagent receipt <invocation-id>` 检查 process、protocol、upstream identity、artifacts 和实际 Read evidence。`PARSED` 不等于 KEEP；项目 Harness、finding adjudication 与 completion 由 Parent 负责。

### Source Stability During Invocation

`inspect` 返回 `frozen_source_paths`，包含 source、适用 instructions、accepted refs、Plan、Harness 和选定 Skill assets，不只是 `read_paths`。从 seal 到 receipt 核验完成期间，Parent 不得修改其中任何文件，也不得派 writer 修改它们；并行工作只可涉及集合外文件。若已有同文件 writer，先按 ownership 规则解决后再 seal，不付费调用一个已知将失效的 snapshot。

每次项目上游请求前重新执行原 seal/snapshot/host 校验；发生 drift 时撤销 invocation，后续请求不再送往 Provider。结束时校验仍保留；检查不是文件锁，不能阻止其他 session 写入，或挽回已经发出的请求。`SOURCE_CHANGED` 不是 timeout，不采用其报告，也不自动重试。若要继续，先稳定整个 frozen set，再由 Parent 新建有理由的有限 attempt。

### New Project Sizing

`kimi-maximum-v1` 是用户明确选择的 global 新项目调用策略，仅在 `inspect` 封存前应用。所有有效新 Kimi task（包括复制旧 task JSON 的较低额度）使用当前 router/pinned runtime 已支持的最高有限额度与 `deep` / max / 1M。`transport.resource_policy` 封存原请求的 profile/budgets，CLI 明确展示原请求与有效结果；task 文件本身不改写。非法值、unknown profile 仍拒绝，read/write paths、permissions、refs 和 acceptance 不变。Gemini 与独立 image contract 不继承此 project-task 策略。

| Budget | Sealed maximum |
| --- | --- |
| `generation_tokens` | 32000 per request，包括 thinking |
| `wall_seconds` | 3600 |
| `idle_seconds` | 1800，Kimi pinned runtime 的上限 |
| `request_limit` | 64，本 invocation 的工具/生成请求总数，不是 review rounds |
| `output_bytes` | 16777216（16 MiB） |
| `context_bytes` | 8388608（8 MiB） |

这些是本地已支持的 ceiling，不是无穷预算或 provider-wide maximum。1M 是所选 profile 的 context 上限，不是生成 tokens 或 bytes；仍投影 minimum sufficient package。额度提高可能增加成本与等待时间，不保证全部消费，也不保证终态报告必然完成。若未来需要恢复更低的新 task 额度，先由用户明确变更该 global policy，不能在 run 中绕过 seal。

### Output Budget

Kimi task 的 `budgets.output_bytes` 限制整条 Claude `stream-json` stdout 与 stderr 的总 bytes，包含 thinking progress、native Read/tool payload 和最终报告；它不是模型 output tokens，也不是 256K/1M context。可省略此字段；maximum policy 在新 seal 中写入 **16 MiB**，Parent 必须检查 inspect 的有效 budgets。其他 wall/idle/request/context budgets 仍须提供有效有限值，但新 seal 按 maximum policy 归一化。

不要用几十 KB 的最终回答长度估算传输预算，也不要失败后机械尝试 1 MiB。历史 seal 的较低额度不调大：live Kimi project seal 低于 **2 MiB** 仍在任何 Provider request 前返回 `OUTPUT_BUDGET_TOO_SMALL`。新 seal 的 maximum policy 不删除现有 **16 MiB** 硬上限。额度不是预付 token 消耗，模型报告仍应简洁、scope 应最小化。

`PROCESS_OUTPUT_LIMIT` 后先检查 receipt 中原始 observed bytes、request count、sealed scope 与预算，再决定是否新建一次有限 attempt；不得自动重试。截断的输出继续隔离，不能将没有 terminal 的 partial findings 当成已完成 review。

### Time And Reporting Budget

新 task 输入可省略 `budgets.generation_tokens`，新 Kimi project seal 的有效值为 **32000**；输入中的显式值仍须为 **1024–32000** 整数，不能靠 normalization 修复非法值。这是每次上游生成的总输出 token（包含 thinking），不是 context 或 stream bytes。旧 seal 的 4096/8192 等较低额度继续严格执行；旧 seal 缺少该额度时 live run 零请求返回 `GENERATION_BUDGET_REQUIRED`。若要应用新 maximum policy，Parent 明确 inspect 一个新 task，不篡改旧 seal、不自动续跑。

Runtime 收到相同 output cap，broker 再对实际 `max_tokens` 执行不增大的上限，并记录 request_max_tokens / generation_token_limit。若 manual thinking budget 与 cap 不兼容则拒绝，不静默削减 thinking。上游 `stop_reason=max_tokens` 或报告的 output usage 超出实际 cap 时，返回 `UPSTREAM_GENERATION_LIMIT`，不交付被截断内容并撤销本 invocation；不自动续写、重试或发起另一轮。上游仍可能在额度用尽前超时，token 上限不构成时延 SLA。

`idle_seconds` 由 supervisor 同时观察 runtime stdout/stderr 和 broker 实际上游接收活动；不是“模型必须在此时间内交出整个答案”。Broker 仍在完整响应验证身份后才交付内容，CLI 自身的等待上限服从 wall budget。完全停滞仍触发 idle timeout；持续 progress/ping 也不能延长总 wall deadline。

项目调用每次 wire request 都附带剩余 wall/request 数量；最后一次可用请求或进入预留收尾时间后为 `FINAL_REPORT`，该次不再提供工具，若上游仍要求工具则拒绝。预算提示由 broker 根据 sealed limits 计算，不修改 model/effort、追加请求或重试。模型必须报告缺失证据，不得编造完成；必需 Read/report 校验保持不变，收尾不保证 acceptance 或必然按时返回。

Parent 的 review package 应聚焦实际风险和 changed boundaries；`expected_evidence` 只列确实必须实际读取的材料，不将所有背景和 Harness stdout 全部变成必读。鼓励批量独立 Reads、避免重复读取；预算不够时缩小一次任务的职责或明确记录未完成检查，不能删掉必要验证来换取通过。失败后先区分 `process.reason` 的 wall/idle 与未完成 wire observation；不要机械加大 timeout 或重新运行同一大包。

## Triggered Implementation Review

连续 Kimi 运行故障后的 native delegation/review 由 `/home/reggie/.codex/SUBAGENTS.md` 的
Repeated Kimi Failure Fallback 与 applicable accepted amendment 管理。Parent 保存 canonical
失败 receipts 后返回 Native Codex 路由；本 Skill/CLI 不自动 retry、切换 backend 或伪造 native receipt。
工程 reviewer 替换不适用于 image qualification 或真实 Provider capability。

本 Skill 不因 Spec、Plan、diff 或 artifact 存在而自行触发 review，也不为 Spec/Plan 默认调用 Kimi。Parent 只有在 repository canonical Spec §9 的 Implementation Review Risk Gate 得出 `KIMI_REVIEW_REQUIRED` 后，才使用本节 mechanics。

Kimi 使用 `reviewer` role 与 read-only permissions，读取 exact final candidate snapshot、applicable accepted Spec/Plan identity、相关 project contract、changed paths/source context、tests/Harness evidence、constraints 与 acceptance criteria。是否 review 仍由 canonical Spec §9 决定；本次 maximum policy 只改变新 invocation 的 sizing/profile，不增加触发频率、付费 attempts 或三轮 review 上限。新 seal 使用 `deep` / max / 1M，输入仍保持 minimum sufficient。初次 review 不包含 Parent 预判；re-review 只增加 previous unresolved findings、Parent resolution、correction evidence 与受影响 contract。Kimi 不得修改 source、Spec、Plan、tests、Harness 或 candidate，不得派生 subagent、commit/push、改变 acceptance criteria 或宣布 completion。

Kimi 只在 canonical 五字段 report 的 `findings` 中输出 findings；每项包含 stable ID、`blocking_candidate` 或 `non_blocking` severity、exact concern、affected path/symbol、violated contract/invariant、concrete snapshot evidence 与 expected correction。`PARSED`、exit 0、空 findings 或 LGTM 只描述 transport/report outcome，不是 acceptance。Parent 按 canonical Spec §9 adjudicate；本 Skill 不自动 retry、不启动第四轮、不拥有 round budget 或 KEEP/REVERT。Semantic fix 需要 Parent 封存新 snapshot 并显式发起适用的 targeted/full re-review。

## Writer

Kimi implementer 只支持一个干净、已跟踪的 owned target，权限 `read,candidate-write`，另传 `--readonly-qualification <canonical-M7-id>`。Worker 仅写 private candidate，不写 host project，不执行测试。

Parent 用 `candidate-test --invocation <id> --argv-json <exact-argv.json>` 在无 broker/key/network 的隔离域测试 sealed candidate，再用 `candidate-apply --invocation <id> --test <test-id>`。Apply 检查 preimage/ownership/hashes，保留 displaced inode/recovery；conflict/unknown 不自动回滚或重试。Parent 核验最终 bytes 并执行项目原生 gates 后作 acceptance。

## Evidence And Limits

### Isolated Image Routes

独立 `image-task/v1` 不继承project task的工具、profile或额度。只有current task明确选择、exact accepted image amendments和单独image config成立时，才使用 `prepare-image-probe`、`qualify-image-route` 或 `run-images`。MiniMax tuple为 `minimax / responses-bounded / MiniMax-M3 / provider-default`，GPT API tuple保持原合同；未知backend拒绝，不将旧Kimi runtime/receipt改名复用。

用户明确使用Codex订阅时，独立tuple为 `codex / subscription-bounded / gpt-6.1-sol 或 gpt-6-luna / high`；当前正式组合为MiniMax+gpt-6.1-sol，gpt-6-luna可单独选择，不自动fallback；旧gpt-6-sol只保留显式兼容和历史证据。需绑定accepted subscription amendment，credential provider为 `codex-subscription`，仅canonical owner读取OS UID home下`.config/jianji/codex/auth.json`并核对access-token account claim与本文件account_id一致；无OpenAI Key前提，不读取global Codex auth、不login/refresh/复制token。其他userData布局拒绝，不搜索同名auth。Docker只收opaque capability。

订阅profile的pre-request generation cap=null，observed output limit=2048不能冒充upstream hard cap。`observe-image-subscription --probe <owned-id> --credential-ref <private-reference>`按固定host的quota/catalog各一次生成canonical account/budget证据；失效登录零查询，缺真实额度/图片权限零model。真实capability仅once、wall180/idle90及原bytes上限，OS UID host ledger不随HOME/state恢复；未知token/cost保持null。工程probe、fake或订阅模型名称均不构成视觉资格，formal预算和产品授权不继承。

`qualify-image-route --native-only`只生成本地fake/实际Docker conformance，不证明模型视觉能力；真实 `--live` 仍必须有独立credential reference、当前认证账号、frozen input accounting和canonical预算。MiniMax当前费用授权为0、budget gate硬拒绝，正式image请求也无费用授权；不得以prepared probe、API连通或native conformance绕过。具体image输入、固定TLS endpoint、hard cap、receipt与资格语义由accepted image Specs和source owners独占；不使用旧MiniMax runner、host CLI或global Codex OAuth回退。

Kimi worker/deep 本机 live route 与两 repo holdout 已有 canonical qualification；deep 实际 1M consumption 未评估。Gemini native/fake 已通过，现有 Code Assist account 返回 `UNSUPPORTED_CLIENT`，两 repo live 仍 blocked。不能把 fake receipts、CLI init、exit 0 或模型自述当成 authenticated identity。

真实 credential 只经 private provider-specific file reference 注入，不进入聊天、argv、prompt 或日志。没有 fallback 到旧 `sub-agents`/MiniMax runner。Follow-up 必须由 parent 检查旧 outcome/artifacts，并新建有理由、独立有限预算的 attempt；禁止删除 budget/consumed records。无自动 accept、revert、commit 或 push。
