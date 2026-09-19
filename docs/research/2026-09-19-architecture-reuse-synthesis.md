# Architecture Research Synthesis

Date: 2026-09-19. Status: research and design exploration; **not a Spec, accepted contract, or implementation plan**.

## Current Truth And Evidence Index

源码检查点为 `a4d4c4e9c28346a92e4102b6c2fe393b4487bec4`，tree `b55fbcf3358177589ebcf941a94c5dacc011fd2f`。本轮没有修改 implementation、runtime/config 或既有 spec/plan。以下四份报告提供来源、精确 SHA、模块、许可证、维护信号、tests、negative reports 和估算；本文件只收敛候选与设计取舍，不复制其完整 catalog。

| Research owner | Contents |
| --- | --- |
| [Current architecture truth](2026-09-19-current-architecture-truth.md) | 当前实现、offline/native/live 区分、receipts、Kimi/Gemini/writer、baseline drift、MiniMax provenance |
| [Routing and dispatch](2026-09-19-routing-dispatch-reuse.md) | CCR、shinpr、两个不同 CodeRouter、LiteLLM、ACP routers、custom/freeform tools、路由负面反馈 |
| [Projection and lifecycle](2026-09-19-projection-lifecycle-reuse.md) | wshobson、AGPair、agent-harness、Agent Skills、AgentPlugins、HF distribution、Tomli-W |
| [Commodity runtime](2026-09-19-commodity-runtime-reuse.md) | AnyIO、HTTPX、ACP Python SDK 的独立机制与适配边界 |

Fresh offline 为 **195 passed / 12 skipped**；开启 local native/containment conformance 为 **207 passed**。后者仅 fake upstream，不是 207 次 live proof。Installed Kimi worker/deep 的 qualification 和 smoke 在本轮读取时有效；Claude `2.1.277` + broker 的 authenticated endpoint observation 可核实 K3 route，但不证明远端权重、实际 max reasoning 或实际 1M consumption。正式 Kimi review 前必须重新验证 freshness。

本轮 Kimi deep 只读现状调查 receipt `f51ac150-9dc4-431d-b3a7-370e8a4cd332` 为 **OUTCOME_UNKNOWN**：第一个 wire 身份已验证，第二个无 terminal identity；它不是完成的审查。Gemini live account 仍 `GEMINI_INELIGIBLE`；M9 partial。Writer 已有 single-existing-file private candidate/test/apply evidence，但 exchange 不是 filesystem CAS，冲突后可能需要 parent recovery。既有 baseline 文件保留为设计输入，不能由“已存在”推出 accepted truth。

## Proposed Composition And Alternatives

建议 **A：按机制组合 OSS，HarnessMesh 保留薄 authority layer**。Process/HTTP/serialization 使用独立库；runtime-native contract 保留原生能力；需要 Claude provider/protocol compatibility 时接入 CCR，且其后必须有独立 egress/identity guard。每个 sealed tuple 有唯一显式路径；有能力注册并不意味着可 live dispatch。

| Approach | Composition | Benefit | Cost / rejection condition |
| --- | --- | --- | --- |
| **A — recommended** | AnyIO + HTTPX + skills-ref/Tomli-W；CCR 用于所需 compatibility；ACP 仅用于已验证的 native session；HM resolve/project/enforce/adjudicate evidence | 没有另一个任务 orchestrator；无需重写通用 process、HTTP、TOML 或已有 transforms；每项可独立升级 | 多个依赖需要明确 owner/pin；native projection 的权限等价不能靠库自动获得。CCR 受限运行尚未 qualification |
| B — CCR-first | 所有 Claude-family provider paths 一律经过 CCR；其余同 A，HM broker 仍是唯一真实 credential/egress owner | Claude compatibility 集中维护，减少多个 protocol path | Anthropic-compatible pass-through 也承担 CCR/Node/依赖的故障面；其 private core startup/logging isolation 必须验证 |
| C — CLI module fork | shinpr builder/parser VENDOR + 单 executor FORK；HTTP/projection 仍用库；CCR 仍可承担 transforms | 可直接复用多 CLI argv/event 分支 | 必须维护 stdout/stderr、descendant cancellation、terminal metadata 修复；AnyIO 已覆盖更成熟的机制，因此该 fork 不是首选 |

这三个方案都不采用 universal giant prompt，也不让 OSS 决定 acceptance、fallback 或任务 scope。A 中的“按需”是安装/qualification 时固定 transport graph，不是运行失败后自动选另一条路径。当前已合格 direct Claude→Kimi 路径不会因为新 research 而被替换或自动标为 CCR 合格。

## Consolidated Reuse Decisions

以下是待 design approval 的 research decisions；所有精确 repo/module/license/maturity/tests/issues 在上方 owner 中。`CUSTOM` 专指下面逐项说明的 authority policy；不能把一个 policy wrapper 的存在说成其底层机制也自研。

| Capability | Mode | Exact surface / decision |
| --- | --- | --- |
| Async CLI lifecycle primitives | WRAP | AnyIO `open_process`, task groups/cancel scopes；外层负责 HM budgets、group/container cleanup、revocation 和 facts。避免 unbounded `run_process` |
| HTTPS / streaming / timeout mechanisms | WRAP | HTTPX `AsyncHTTPTransport` + `AsyncClient`，固定 URL/SSL、禁 inherited proxy/redirect/retry；不把 model 判断放进 HTTP library |
| Claude protocol/provider compatibility | WRAP | CCR pinned core/gateway distribution。单 broker egress、无真实 key、禁插件/嵌套派发/自动 fallback；broker 先记录 raw upstream identity 再让 CCR 转换 |
| Runtime-native CLI argv/event mapping | VENDOR | shinpr `_builder.py` / `_stream.py` 的明确子集，排除 raw credential loader、permission defaults、executor；每个 CLI/profile 单独 conformance。没有宣称全文件可直接采用 |
| Native ACP protocol | WRAP | official Python SDK `ClientSideConnection` / `Connection`，使用 parent-owned streams；不引入 SDK spawn convenience 或第三方 ACP controller |
| Portable Skill envelope | DIRECT | `agentskills/agentskills/skills-ref` parse/validate；native extensions 由 target schema 独立解释，不能被 silently stripped 或误报为通用 core 有效 |
| Native TOML serialization | DIRECT | Tomli-W `dumps(multiline_strings=False)`；稳定输入排序 + parser roundtrip，不编辑既有项目配置 |
| Multi-harness text drift advisor | WRAP | `@madebywild/agent-harness-framework` public `plan({cwd})`，仅 synthetic read-only text workspace；不是完整 renderer，暂不作为默认必需依赖 |
| Full projection/receipt/controller frameworks | REFERENCE_ONLY | wshobson full traversal/emitter、HF publisher、AGPair receipt/recovery、CodeRouter controller、AgentPlugins compiler；具体拒绝理由见分报告。并非排除所有未来 module reuse |
| Provider API gateway alternative | WRAP | LiteLLM constrained sidecar，仅未来确需的 provider API translation；不与 CCR 默认叠加 |
| Additional Rust gateway | REFERENCE_ONLY | superagent-ai/gateway 功能契合，但固定源码没有适用 license declaration；不能执行性复用其代码，待 license evidence |
| Filesystem/hash/JSON/storage mechanisms | DIRECT | 当前 Python stdlib 和 Linux/Docker 机制仍是可复用 primitives；研究未选择另一个 orchestration DB。HM receipt association/recovery policy 的 CUSTOM 理由如下 |

Provider、runtime、model、profile、backend adapter 必须在设计中分别建模。例如 provider=Kimi / runtime=Claude Code / client model=`k3[1m]` / upstream model=`k3` / profile=`deep`，不是一个模糊的“Kimi backend”。CC Switch 是本机 credential 配置输入，既不拥有 route acceptance，也不把 key 传进模型 contract。

## CUSTOM Burden Of Proof

没有成熟 OSS 被证明覆盖整个 authority contract 的约 80%；也没有证据允许以此为由重写 commodity infrastructure。建议仅保留下列 HM policy。数值为候选总责任的 production/tests LOC 估算（至少 ±35%），包含可能保留/调整的现有代码，**不是新增量、实现承诺或 roadmap**。具体逻辑若可移入前述库，应从此表扣除。

| Policy / exact unmet behavior | Why DIRECT does not suffice | Why WRAP does not eliminate the custom policy | Why VENDOR does not suffice | Why FORK is worse here | Estimated production / tests LOC; maintenance and breaking-change owner |
| --- | --- | --- | --- | --- | --- |
| **Project contract resolution and authority projection**：parent-selected accepted refs、scoped constitution/task/runtime 三层、source closure、precedence、owned paths 与 native capability rejection | skills-ref 只验证 Skill envelope；wshobson field filtering 丢 native 权限；agent-harness model/registry 不含 HM accepted-ref seal | 可包住 parser/renderer，但 wrapper 仍须决定哪些 project refs 已授权、哪些 semantic field 不可投影；这就是要保留的 policy | 复制 `codex.py` field maps 或 `planner.ts` operations 没有增加上述 authority predicates，且前者有实测 string drift | 给第三方 compiler 加 HM project-truth semantics 会绑死其 schema/registry；使用 typed seam 可独立升级机制 | **300–450 / 400–600**。HM 拥有 resolver/native permission mapping 和兼容 fixtures；upstream 拥有语法。每次 native discovery/precedence 改变须重新 qualification，不能 silent strip |
| **Delegated admission / credential capability / qualification policy**：sealed tuple、allowlisted provider/model/tools、fresh evidence、最小权限、nested deny、fail closed | AnyIO/HTTPX 不解释项目授权；CCR default routes、AGPair executor defaults 不满足该 policy | 推荐 WRAP 正是复用机制，但仍须新增 seal/capability/deny predicates；不把这些交给模型生成 | vendor defaults 会保留 fallback/permission 语义；修订后仍是 HM 专属 policy | fork gateway/runner 会把安全授权复制到多个 backend control planes；外部单一 admission/egress owner 更少 drift | **200–350 / 300–500**。HM 拥有授权、revoke、freshness 和版本准入；upstream 拥有 transport bugs。新增 endpoint/runtime 必须审查，不自动继承旧资格 |
| **Evidence association / identity acceptance / receipt recovery**：绑定 invocation、project、source/candidate、per-wire request/response、process/parse/identity 独立维度与 unknown | CCR response rewrite、CodeRouter configured model、AGPair delivery dedup 都缺这些 association；可复用 JSON/hash/fs 机制 | broker 捕获 raw response 可行，但怎样关联并接受证据仍需 HM policy；不能要求库替 parent adjudicate | vendor 上述 attribution/recovery 函数不会获得缺失 seal、freshness 或 unknown 语义 | fork 任何一个 gateway 无法自然覆盖 CLI/ACP/parent candidate lifecycle；会产生多 receipt truth owner | **250–400 / 400–650**，其中 identity predicates **140–220 / 180–300** 已含在内，勿重复相加。HM 拥有 schema/version/recovery；普通序列化与文件操作复用标准机制。目标是 authenticated endpoint evidence，不是远端权重证明 |
| **Candidate disposition and apply authorization**：exact preimage、owned path、candidate/test hash、并发修改、unknown/recovery；KEEP/REVERT 只由 parent | agent-harness `apply` 顺序写 UTF-8，AGPair recovery 可以由 agent action 选 use_result；二者不具 exact candidate→test→apply contract | 可以调用 OS 原子 rename/exchange，但是否允许 apply、冲突如何保全与关闭仍需 HM policy | vendor `engine.ts:apply`/AGPair recovery 不能提供 missing source/test binding；需重写核心语义 | fork full harness 为单文件受控候选添加独立 parent authority，收益小于保留 isolated policy + OS primitives | **180–300 / 300–500**。HM 拥有 apply preconditions、readback/recovery 和迁移；Linux/容器机制不自研。多文件事务/自动 rollback 不在当前合格范围 |

表内四项合计候选 policy **930–1500 production / 1400–2250 tests LOC**；不是对当前 5420 physical source LOC 的删除承诺。维护风险更低的依据是：机制由上游维护，HM policy 一处解释，避免在每个 gateway/CLI fork 重复实现。最终 Spec 必须为每项指定唯一 normative owner；若实际设计开始重写 generic process/HTTP/TOML/router，此研究结论需要重新打开。

## Proposed Contract Ownership For Design Discussion

这张表是未来 Spec 的职责划分候选，不是另一套 normative contract。实现文件、research 和历史 status 各自保持原 ownership。

| Design concern | Proposed single owner | Key boundary to settle |
| --- | --- | --- |
| User / parent / project truth | Parent and project-native accepted contracts | HM subordinate；project Harness、AC、Skills authority 不由外部 worker 或 OSS 重定义 |
| Contract resolution | HM Project Contract Resolver | repository root/constitution、current task/accepted refs、runtime protocol 分离；scoped minimal deterministic projection；缺必要 ref/不支持 native semantics 就 reject |
| Invocation admission and isolation | HM delegated authority policy | 唯一 sealed runtime/provider/model/profile/tool graph；role read-only 或已 qualified candidate writer；denied nested delegation，不通过 prompt alone 保护 |
| Process and wire facts | HM supervisor/egress evidence policy over OSS mechanisms | request identity、runtime version、exit/timeout/retry/output/candidate/parse/budget 由 deterministic layer 记录；模型输出 findings/uncertainty |
| Semantic report | External worker | findings/references/questions/proposals；不生成“transport success / actual model / accepted”作为事实来源 |
| Receipt and recovery | HM execution evidence owner | association + atomic persistence；last observation 不冒充 terminal；unknown outcome 冻结 candidate/apply，不自动重试有副作用的任务 |
| Candidate test/apply | Parent-controlled candidate gate | isolated tests、exact tested candidate、concurrent-change check、apply readback；若已发生 exchange 冲突，显式记录实际 bytes 与保留的用户数据，禁止承诺零 mutation |
| Completion | Parent + project-native Harness + exact user approval | reviews 只有 findings；blockers 逐项 evidence adjudication；PARSED/exit0/valid JSON 皆不拥有 acceptance |

Secret boundary 应包括真实 credential 和 ephemeral capability：只在 broker/runtime 的私有受控通道注入；不进 repository、prompt、semantic report、receipt、diagnostic 或 artifact/log。Model-visible contract 只表达 capability 是否获授。未经检查的任意 source document 不能因为路径合规就视为不含 secret；密钥发现/泄漏时应拒绝该输入或关闭输出交付，不能通过“redacted 一次”宣称绝对完备。

MiniMax 提供的主要设计教训是 **transport state 不由 model report 决定**。Legacy `DONE_WITH_CONCERNS` + non-empty questions 的语义冲突保持失败；换 envelope 不得把历史 failure 追认通过。只有具有唯一解释的 representation normalization 才可机械完成；string `"null"`、缺 terminal、tool mismatch、矛盾问题/完成声明都不能猜意图。Read-heavy findings 仍可能有价值，但 evidence gaps 和错误架构结论须单独暴露给 parent，避免把 parse success 变成工作完成。

## Qualification And Version Strategy

依赖批准绑定 exact upstream commit、发布 artifact digest、license/notice 和 transitive lock；version label 与 inspected HEAD 不是同一物。任何 package/runtime/config/credential/route/tool semantics 变化，应按具体 qualification fingerprint 失效相应证据。上游 issue 是 regression 输入；open/closed、star、README 或同名 preset 都不是合格证据。

需要的验证层次是机制 tests → native fake-upstream conformance → explicit bounded live tuple qualification → project-native task/Harness evidence；没有该层 evidence 就保留未验证状态。它们是验证类别，不是本轮 implementation plan。必须覆盖 wrong-model/alias mismatch、CCR metadata/freeform tool translation、unknown terminal、stdout/stderr backpressure、cancel descendants、credential leak paths、nested delegation、binary/mode fidelity、concurrent candidate apply/recovery。

Research probes 已有 AnyIO 三例 PASS、wshobson 两个可复现 emitter 缺陷、Tomli-W 268 passed/2 expected xfail 加六例 roundtrip。CCR restricted sidecar、agent-harness text wrapper、ACP native sessions、shinpr subset 均未在 HM 集成，不能据此宣称 Kimi/GLM/MiniMax/Grok/Gemini 全部可用。

## Workflow Checkpoint

已完成 context/reuse investigation，正在 `superpowers:brainstorming` **Architectural** approaches/sectioned-design gate。尚未向用户取得本轮设计批准，尚未写 formal Spec；Spec Self-Review、exact Spec freeze、双独立 Spec review 和 written-spec User Review Gate 均未开始。

两名 native research agents 完成初稿后，补充调查受 account usage limit 中断；parent 已接手并复核上述关键结论。这不是独立 Spec review，也不能拿以前 timeout/policy reviewer 的结果替代。最终 reviewer A 应 fresh read-only `reviewer_xhigh`（Astra/xhigh），reviewer B 应已重新验证资格的 Kimi `deep`/max；只有未来真正调用时才记录实际 model/snapshot/result。

Research checkpoint 的 parent 检查覆盖五份文档的 local links/whitespace，以及 67 个去重的 pinned GitHub source links 对应的 clone Git objects，均可解析；没有以链接存在代替结论正确性。没有专用 session-capture skill；本 research 目录就是此次研究的 durable artifact，未创建重复的运行状态 owner。

下一流程动作是提交 A/B/C 取舍与第一段 architecture/authority design 供用户批准；不写 plan，不实现。按已读 Skill 的 “get user approval after each section”，设计段落批准后继续其余设计讨论，再写 Spec。未来完整 Spec 经 self-review 后封存 exact SHA 与共同 evidence snapshot，双侧互不可见；任何修改都重跑双方，parent 逐项裁决后才请求最终用户批准该 SHA。本 checkpoint 不是 accepted Spec，也不是最终 written-spec approval gate。
