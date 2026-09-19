# Projection and Lifecycle Reuse Research

## Decision

`agentskills/agentskills` 的 Python `skills-ref` parse/validate edge 是可独立采用的候选；它符合 Python runtime、Apache-2.0 和 Agent Skills public contract。Parent 补查了 Tomli-W，用于成熟 TOML serialization。两者都不拥有 runtime authority；本报告没有批准或引入依赖。

其余发现应分开处理，不能因 whole-stack 不适配就断言其子模块不可复用：

1. `wshobson/agents` 的小型 emitter 已逐函数检查，但 TOML roundtrip probe 暴露真实缺陷；该 emitter 改为 **REFERENCE_ONLY**，TOML 机制优先 Tomli-W **DIRECT**，不自行重写 escaping；
2. `madebywild/agent-harness` 公共 `plan()` 是 text-only synthetic workspace 的 **WRAP candidate**；内部 `buildPlan` 既未公开 export 又会读现有文件，不能描述成纯 JSON→JSON API；
3. `huggingface/skills` byte publisher 与 AGPair receipt/recovery 目前为 **REFERENCE_ONLY**：前者缺 mode contract 并绑定 distribution semantics；后者存的是 task/message delivery，而不是 sealed execution evidence。已有实现并不自动排除替换；这里拒绝的是具体不匹配的模块；
4. subprocess/cancel/timeout/credential 在本报告仅记录 AGPair 的不适配证据；AnyIO/ACP 等机制由 [commodity runtime report](2026-09-19-commodity-runtime-reuse.md) 单独比较，不在这里重复选择。

这不是采用任何一个上游的 whole-stack harness，也不是 implementation plan。Codex、Claude 与 Gemini 的 native 文件、权限、hooks、安装位置和实际运行时加载仍须由现有 canonical owner 保持；project Harness、credential broker、upstream identity proof 和 parent-only acceptance 也不能委托给这些组件。

## Research Method And Scope

本报告于 **2026-09-19** 对公开 default-branch HEAD 做了 shallow source inspection，并通过 GitHub REST metadata、releases、contributors、open issues/PRs 与 default-branch commit history 复核维护信号。所有源码链接固定到下列 SHA；stars、forks、活动和 issues 是该日期快照，不是未来维护承诺。

- 只研究；没有安装上游依赖、执行上游 install/postinstall、调用 Provider、修改运行配置或生成最终 spec/plan。
- `30d/90d commits` 是 `git log --since` 在分别 fetch 到日期边界后的 default-branch reachable commits，不把 issue/PR 数误报为 commit 数。
- `tests` 默认表示源码中存在且审阅过的测试面；parent 后续实际执行的 emitter probes 与 Tomli-W tests 单列在文末，其余不能称为通过。

## Current Upstream Snapshot

| Project | Fixed source | License | Stars / forks | Contributors | Releases | 30d / 90d commits | Open issues / PRs | Maintenance assessment |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | --- |
| [wshobson/agents](https://github.com/wshobson/agents/tree/4236bb91f8395b0435f1d8b8baf9e8e4c69a8620) | `4236bb9` | MIT | 39,796 / 4,245 | 79 | none | 22 / 88 | 11 / 6 | 活跃；9 月仍有 adapter/CI 修改。 |
| [logicrw/agpair](https://github.com/logicrw/agpair/tree/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98) | `755d4b2` | MIT | 48 / 0 | 1 | none | 0 / 6 | 0 / 0 | 单维护者且自 6 月无新 default-branch commit；维护风险较高。 |
| [madebywild/agent-harness](https://github.com/madebywild/agent-harness/tree/2ecf44f97ab6ffd76f5c1a58ac57b930e2ccfa17) | `2ecf44f` | MIT | 13 / 0 | 4 | 8; latest [v2.1.0](https://github.com/madebywild/agent-harness/releases/tag/v2.1.0) | 2 / 11 | 3 / 1 | 最近发布 9 月 1 日；v2.0 registry/prompt-section 已发生 breaking refactor。 |
| [agentskills/agentskills](https://github.com/agentskills/agentskills/tree/69ef37e9424c0a7ea9dd2293b559e43ec8176379) | `69ef37e` | Apache-2.0 | 25,510 / 1,917 | 41 | none | 0 / 20 | 79 / 39 | 规范与 reference library；有近期 review 活动但 default branch 8 月后未更新。 |
| [anthropics/skills](https://github.com/anthropics/skills/tree/34040c9c568585f6929bedeaad110ad08f079624) | `34040c9` | repository metadata `NOASSERTION` | 177,109 / 20,985 | 15 | none | 0 / 1 | ≥100 / ≥100 (API page cap) | 高活跃内容库，但根仓库没有可验证的 reusable license；不要 vendor whole repository。 |
| [sigilco/agentplugins](https://github.com/sigilco/agentplugins/tree/f3d9c439680d26d4316c1ed214ae9a82a2127a2a) | `f3d9c43` | Apache-2.0 | 10 / 1 | 1 | 6; latest [v0.6.1](https://github.com/sigilco/agentplugins/releases/tag/v0.6.1) | 0 / 1 | 34 / 0 | 6 月以后无持续代码活动；未关闭 issue 数远高于维护规模。 |
| [huggingface/skills](https://github.com/huggingface/skills/tree/abc20ae526d8b4c0e4dff89f904adce28a4a0eb6) | `abc20ae` | Apache-2.0 | 11,068 / 745 | 42 | none | 4 / 32 | 58 / 48 | 活跃，近期同步和安全修正；有清晰的小型 Python distribution builder。 |

上述 metadata 的公开 owner pages：[`wshobson/agents`](https://github.com/wshobson/agents)、[`logicrw/agpair`](https://github.com/logicrw/agpair)、[`madebywild/agent-harness`](https://github.com/madebywild/agent-harness)、[`agentskills/agentskills`](https://github.com/agentskills/agentskills)、[`sigilco/agentplugins`](https://github.com/sigilco/agentplugins)、[`huggingface/skills`](https://github.com/huggingface/skills)。

### Issue And PR Activity For The Three Primary Candidates

`open issues / PRs` 是库存，不是活动。下表使用 GitHub issue-search 的日期筛选：30 天窗口始于 `2026-08-20`，90 天窗口始于 `2026-06-21`；`issue` 排除 PR，`merged` 按 `merged:` 过滤。该 API 在补取 `agent-harness` 的 90-day issue 数据时达到 rate limit，因此该两格明确保留为未测量，而不是填零。

| Project | Window | Issues created / updated | PRs created / updated / merged | Reading |
| --- | --- | ---: | ---: | --- |
| `wshobson/agents` | 30d | 9 / 11 | 30 / 34 / 20 | 持续有变化；与 22 commits 不同，PR activity 表明细粒度协作活跃。 |
|  | 90d | 34 / 39 | 79 / 93 / 69 | 维护与合并都明显活跃。 |
| `logicrw/agpair` | 30d | 0 / 0 | 0 / 0 / 0 | 无公开活动。 |
|  | 90d | 0 / 0 | 0 / 0 / 0 | 单维护者停滞证据与 commit history 一致。 |
| `madebywild/agent-harness` | 30d | 1 / 1 | 1 / 2 / 2 | 仍有低频 issue/PR 活动。 |
|  | 90d | **not measured (API rate limit)** | 6 / 7 / 7 | 已测 PR activity 显示 release 后仍有合并；未测 issue 数不得推断。 |

## Native Projection Evidence

`SKILL.md` 是 portable content envelope，不是 portable runtime contract。Agent Skills v1 的 required core 仅是 `name` 和 `description`；`license`、`compatibility`、`allowed-tools`、`metadata` 都是有限的 optional surface。[reference models](https://github.com/agentskills/agentskills/blob/69ef37e9424c0a7ea9dd2293b559e43ec8176379/skills-ref/src/skills_ref/models.py#L7-L39) 与 [validator allow-list](https://github.com/agentskills/agentskills/blob/69ef37e9424c0a7ea9dd2293b559e43ec8176379/skills-ref/src/skills_ref/validator.py#L10-L22) 都支持这个边界。因此标准 validator 能保证 bundle 的基线合法性，却不能证明某 agent 的 permissions、hooks、model、MCP、subagent 或 sandbox 表达等价。

| Runtime | Source-backed difference | Projection consequence |
| --- | --- | --- |
| Codex | `wshobson` 生成 `.codex/skills/*/SKILL.md` 和 agent TOML，并刻意不生成 root `AGENTS.md`；其 adapter 明确剥离 Claude-only skill/agent fields。[source](https://github.com/wshobson/agents/blob/4236bb91f8395b0435f1d8b8baf9e8e4c69a8620/tools/adapters/codex.py#L1-L13) [field loss](https://github.com/wshobson/agents/blob/4236bb91f8395b0435f1d8b8baf9e8e4c69a8620/tools/adapters/codex.py#L34-L52) | Codex projection 必须是独立 output，并拒绝把 ignored fields 伪装成已执行的权限；项目 `AGENTS.md` 必须仍由其 canonical owner 管理。 |
| Claude | 同一上游会把 Claude commands 转为其 native artifact；Claude 独有的 `allowed-tools`、`hooks`、`model` 等无法无损落在 Codex。[same adapter field set](https://github.com/wshobson/agents/blob/4236bb91f8395b0435f1d8b8baf9e8e4c69a8620/tools/adapters/codex.py#L34-L52) | Claude 的 source field 要保留并由 Claude renderer 处理；不得先降级为 generic markdown 再反向声称 native enforcement。 |
| Gemini | AgentPlugins 的 Gemini adapter 实际输出 `gemini-extension.json` 与 hooks JSON wrapper，并规定 exit `0=allow`, `2=block`, other=`warning`。[adapter contract](https://github.com/sigilco/agentplugins/blob/f3d9c439680d26d4316c1ed214ae9a82a2127a2a/packages/adapter-gemini/src/index.ts#L1-L20) | Gemini 不是 Codex/Claude 的换路径副本：其 hook semantics 和 extension manifest 需要单独 contract tests；非 0/2 的 warning 不能被推断为 fail-closed。 |

## Capability Reuse Matrix

`Mode` 只使用如下受控词：`DIRECT` 直接依赖可隔离模块；`VENDOR` 固定 SHA、保留 license/notice 并维护小段 upstream 代码；`WRAP` 通过窄接口调用组件；`FORK` 维护上游分支；`REFERENCE_ONLY` 只采纳设计/测试思路；`CUSTOM` 须逐项证明 DIRECT/WRAP/VENDOR/FORK 不能承担该项职责。

| Capability / needed behavior | Candidate exact module and license | Maintenance, tests, issues | Adaptation and reuse mode | Decision and reason |
| --- | --- | --- | --- | --- |
| **Skill schema gate**：解析 `SKILL.md`、拒绝未知 frontmatter、检查 name/path、长度和 Unicode。 | `agentskills/agentskills` [`skills-ref`](https://github.com/agentskills/agentskills/tree/69ef37e9424c0a7ea9dd2293b559e43ec8176379/skills-ref), Apache-2.0. | 41 contributors, 20 commits/90d, 79 issues/39 PRs；有 parser/validator/prompt tests。 | Python `DIRECT` candidate: fixed SHA import parse/validate；仅用 facade 转 typed diagnostic，不用其 Anthropic XML prompt renderer。 | **DIRECT candidate**，不是已批准依赖；`strictyaml` dependency 需要独立审查。 |
| **Whole Skill bundle integrity**：递归枚举 resources，原始 bytes digest，并保留 executable mode。 | `huggingface/skills` [`build_skill_distribution.py`](https://github.com/huggingface/skills/blob/abc20ae526d8b4c0e4dff89f904adce28a4a0eb6/scripts/build_skill_distribution.py#L101-L180), Apache-2.0. | 42 contributors, 32 commits/90d；[tests compare published bytes/digests](https://github.com/huggingface/skills/blob/abc20ae526d8b4c0e4dff89f904adce28a4a0eb6/scripts/test_build_skill_distribution.py#L73-L100)。 | 348 production / 137 test LOC are inspected whole-file sizes, not selected reuse. Publication discovery/digest 不含 HM executable-mode/authority contract；byte copying/hashing 本身可继续复用 stdlib。 | **REFERENCE_ONLY** for publisher；无新增 publisher owner。已有 projection 也需接受模式、source preimage 与 native activation 检验。 |
| **Plan-only native drift calculation**：render text target artifacts, classify create/update/delete/noop, reject unmanaged collision. | `madebywild/agent-harness` public [`index.ts:plan`](https://github.com/madebywild/agent-harness/blob/2ecf44f97ab6ffd76f5c1a58ac57b930e2ccfa17/packages/toolkit/src/index.ts), internal [`planner.ts:buildPlan`](https://github.com/madebywild/agent-harness/blob/2ecf44f97ab6ffd76f5c1a58ac57b930e2ccfa17/packages/toolkit/src/planner.ts#L208-L314), MIT. | 4 contributors, 11 commits/90d, v2.1.0; collision/settings/provider tests; v2.0 registry change. | **WRAP candidate** only through public `plan({cwd})` over parent-prepared, read-only, text-only synthetic workspace. Public result omits rendered bodies; internal `buildPlan` requires non-public imports and reads disk. Binary assets/modes remain outside. | **Conditional WRAP** for text drift advisory, not a complete compiler. Direct renderer reuse would need bounded VENDOR/FORK with separate evidence; no claim that such a package already exists. |
| **Codex TOML/frontmatter emitter**：preserve semantic values without acquiring content/asset ownership. | `wshobson/agents` [`codex.py` render helpers](https://github.com/wshobson/agents/blob/4236bb91f8395b0435f1d8b8baf9e8e4c69a8620/tools/adapters/codex.py#L55-L102), MIT. | 79 contributors, 88 commits/90d; parent probe below reproduces newline drift and invalid CR string. | Do not vendor faulty `_toml_kv`; retain native mapping/test ideas. `_frontmatter_block` is described upstream as YAML-ish, not a complete serializer. | **REFERENCE_ONLY** for these helpers; mature TOML serializer DIRECT is lower maintenance than fixing a second writer. |
| **Multi-harness manifest schema**：represent target-specific capability differences. | `sigilco/agentplugins` [`manifest.schema.json`](https://github.com/sigilco/agentplugins/blob/f3d9c439680d26d4316c1ed214ae9a82a2127a2a/spec/v1/manifest.schema.json#L1-L125), Apache-2.0. | One contributor, 1 commit/90d, 34 issues; Codex/Claude tests exist, Gemini package lacks a test script; [#54](https://github.com/sigilco/agentplugins/issues/54) reports advertised agent output is absent. | Preserve target matrix/negative fixture ideas; its `nativeEntry` is an escape hatch, not compiler completeness.[source](https://github.com/sigilco/agentplugins/blob/f3d9c439680d26d4316c1ed214ae9a82a2127a2a/spec/v1/manifest.schema.json#L192-L210) | **REFERENCE_ONLY**。无足够维护或 Gemini evidence 支持 wrap/fork。 |
| **Receipt/recovery vocabulary**：idempotency, artifact-vs-agent result, inspect/review/retry distinctions. | AGPair [`receipts.py`](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/agpair/storage/receipts.py#L31-L62) / [`recovery.py`](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/agpair/recovery.py#L66-L200), MIT. | One contributor, 0 activity in 30/90d, no releases. | Its 62 production LOC `ReceiptRepository` requires SQLite and creates a second persistence owner; it cannot preserve current [`ReceiptStore`](../../src/agent_subagent_router/receipts.py) private filesystem, sealed-artifact and finalization association invariants. Its 201-LOC recovery function selects/switches executors. | **REFERENCE_ONLY**。No AGPair LOC is selected for reuse; `263` is an upper-bound inspection count, not reuse sizing. |
| **Subprocess/cancel/timeout/credentials**：bounded child lifecycle and typed receipt. | AGPair local executor starts from `os.environ.copy()`.[source](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/agpair/executors/local_cli.py#L744-L771) AgentPlugins splits command strings on whitespace.[source](https://github.com/sigilco/agentplugins/blob/f3d9c439680d26d4316c1ed214ae9a82a2127a2a/packages/compile/src/emit.ts#L14-L26) | AGPair inactive; AgentPlugins has low activity and no Gemini test script. | Both are negative candidates only. This report did not inspect stdlib/AnyIO/ACP process components, so it cannot compare their reuse modes or LOC. | **REFERENCE_ONLY** for the two inspected sources; **no `CUSTOM` decision**. |
| **Controlled candidate apply**：exact owned path/preimage, concurrent edit detection and explicit recovery. | HM [`atomic_apply.py`](../../src/agent_subagent_router/atomic_apply.py); upstream `agent-harness` [`engine.ts:apply`](https://github.com/madebywild/agent-harness/blob/2ecf44f97ab6ffd76f5c1a58ac57b930e2ccfa17/packages/toolkit/src/engine.ts#L526-L580) is text-only sequential writing. | Current tests show exchange may mutate target before detecting a race; it is not compare-and-swap. Upstream has no corresponding atomic candidate contract. | Reuse OS filesystem mechanisms, define parent recovery policy separately. Projection materialization and trusted-workspace candidate apply have different authority and must not be conflated. | **REFERENCE_ONLY** for upstream apply; CUSTOM policy burden belongs to synthesis, not an assumption that current implementation is accepted. |

## Rejected Whole-Stack Paths And Negative Evidence

### `wshobson/agents`

这个项目是最有价值的 **static projection reference**，不是可直接引入的 runtime. 它正确保留 root `AGENTS.md` ownership，但其 Codex adapter 明确删去 Claude fields；`inherit` 的静态 model resolution 和 allowlist-to-sandbox 降级都不是权限等价。更重要的是，source 中 `_emit_skill` 只列 `SKILL.md` 和 `references`，所以具有 scripts、templates、binary assets 或 executable bits 的 Skill 无法证明完整转运。[emission implementation](https://github.com/wshobson/agents/blob/4236bb91f8395b0435f1d8b8baf9e8e4c69a8620/tools/adapters/codex.py#L361-L398)

结论：使用其 target fixture、generated-diff CI 与 owner-boundary ideas。Whole generator 的 traversal/model/permission defaults 不适配，不代表所有子模块都不能复用；具体 emitter 由下面的可复现实验淘汰。静态 TOML parse 仍不等于 Codex agent 实际 activation。

### AGPair

AGPair 贡献的是可剥离的 receipt/recovery 分层。`ReceiptRepository.record` 使用 message PK 与 `(task_id, delivery_id)` 唯一键，适合防重放；`RecoveryDecision` 也区分 `use_result`、`review_then_apply` 和 `inspect_evidence`。[receipt dedup](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/agpair/storage/receipts.py#L31-L62) [decision model](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/agpair/recovery.py#L66-L200)

不能继承的是 controller/executor control plane：AGPair 的 Codex default 是 `--dangerously-bypass-approvals-and-sandbox`，Claude default 是 `bypassPermissions`。[Codex source](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/agpair/executors/codex.py#L9-L15) [Claude source](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/agpair/executors/claude_code.py#L19-L23) 这些默认、environment inheritance 与 recovery executor switch/fallback 不符合本任务边界。即便单独剥离纯函数，`choose_recovery_decision` 仍包含 agent `controller_action`→`use_result` 等业务 policy；本轮没有选择 vendor 该代码。`ReceiptRepository` 是 SQLite message-delivery dedup，不能把 session id 或 delivery acknowledgment 说成 Provider receipt。

### `madebywild/agent-harness`

其 planner 的 unmanaged-collision refusal 与 create/update/delete/noop 是有用的 safety property。[planner behavior](https://github.com/madebywild/agent-harness/blob/2ecf44f97ab6ffd76f5c1a58ac57b930e2ccfa17/packages/toolkit/src/planner.ts#L255-L314) 但 loader 对每个 asset `readFile(..., "utf8")`，apply 同样写 UTF-8；不能覆盖任意 binary bytes/executable modes，普通 UTF-8 script text 不因此自动损坏。Public `plan()` 会经过 loader，返回 operations/diagnostics/nextLock，不返回 artifact bodies。内部 `buildPlan` 又会 `readTextIfExists`，因此不能假定用一个 JSON wrapper 就得到无 I/O 的完整 renderer。限制为 text-only snapshot drift advisor 是 WRAP 候选；如果要作为完整 native projection 基础，需额外 export/byte-resource 的具体 upstream adaptation evidence。目前不把它的 managed lock 引入业务项目 constitution。

### AgentPlugins

它明确包含 Codex、Claude、Gemini adapter，且是 Apache-2.0；但观察窗口内代码活动很少、单维护者、34 open issues，Gemini package 没有 test script。其 Gemini adapter 的 exit-code contract 也说明不同 runtime 的 failure semantics 不能被 flatten。当前更适合提供 target matrix 和 tests 反例，尚无足够 evidence 选择为 HarnessMesh runtime-native projection dependency。

### Agent Skills standard and `anthropics/skills`

`agentskills/agentskills` 的 Apache-2.0 reference library 是适合 `DIRECT` 的标准 edge。相比之下 `anthropics/skills` 的 repository metadata 不声明 license；即使许多 individual skills 有 license text，也不能泛化成整个 repo 可 vendor 的许可。前者验证 package envelope，后者可作为 content/example source，但二者都不处理 subprocess、MCP credentials、timeout/cancel 或 provider receipts。

## Reuse Budget And Ownership

| Slice | Inspected upstream production LOC | New adapter production / tests LOC | Accounting boundary |
| --- | ---: | --- | --- |
| Agent Skills parse/validate (`models`, `parser`, `validator`, `errors`) | 353 | 30–60 / 70–120 | DIRECT candidate; imported implementation plus `strictyaml` pinned separately. No generic XML prompt renderer. |
| Tomli-W writer | 229 | 10–25 / 30–60 | DIRECT candidate; serializer only, no permission or model projection logic. |
| agent-harness public text drift API | toolkit dependency, not counted as copied LOC | 100–180 / 150–250 | Optional WRAP over synthetic text snapshot; Node and transitive qualification required. Not complete artifact compiler. |
| wshobson emitter, HF publisher, AGPair receipts/recovery | 0 selected for executable reuse | 0 | REFERENCE_ONLY; their inspected file sizes must not inflate a reuse claim. |

这是 candidate sizing，误差至少 ±35%；不计算 dependency graph 的总执行代码，不宣称达到 80% whole-product coverage。Process/HTTP/ACP 机制见 [commodity runtime report](2026-09-19-commodity-runtime-reuse.md)，HM irreducible policy 的逐项 CUSTOM burden 见 [synthesis](2026-09-19-architecture-reuse-synthesis.md)。不能用“没有一个项目同时满足所有需求”来证明任何单项机制必须自研。

## Parent Probe And Serializer Alternative

Parent 将 fixed wshobson source 的 `_escape_toml_basic`、`_escape_toml_multiline`、`_toml_kv` 原样经 AST 提取执行，再用 Python `tomllib.loads` 读取：`line1\nline2` roundtrip 增加一个末尾换行；`line1\rline2` 产生 `TOMLDecodeError`；普通单行字符串通过。该三例是 **本轮复现**，不是对全部 upstream adapter tests 的评价。它说明低 LOC 的 hand-written helper 不一定值得维护一个 fork。

继续搜索得到 [hukkin/tomli-w](https://github.com/hukkin/tomli-w/tree/1210bb6f5708a4dc084cc3deb4a3a3e3939f4d6d)：MIT、143 stars / 21 forks / 7 contributors，default HEAD `1210bb6f5708a4dc084cc3deb4a3a3e3939f4d6d`（2026-01-17）；GitHub latest-release endpoint 没有返回 release，PyPI [1.2.0](https://pypi.org/project/tomli-w/1.2.0/) 发布于 2025-01-15。2026-09-19 GitHub API 的 30d/90d commits 是 0/0，issues updated 0/1、PRs updated 4/4。维护者 Taneli Hukkinen；发布慢，但其作用域很小、有持续 PR 活动。Pinned package 没有 runtime dependencies，build tool 不因此获运行权限。

Exact reusable surface 是 [`src/tomli_w/_writer.py::dumps`](https://github.com/hukkin/tomli-w/blob/1210bb6f5708a4dc084cc3deb4a3a3e3939f4d6d/src/tomli_w/_writer.py)（229 physical LOC），模式 **DIRECT**。Needed behavior：把经过 HM native-schema gate 的 Python mapping 序列化为 TOML，原字符串值可 roundtrip；adapter 使用 `multiline_strings=False`、稳定 key order，再用标准 parser 验证，不编辑用户已有 TOML。它不保留 comments，不保证任意恶意 Python object 都生成合法 TOML，不证明 Codex native schema。

Known compatibility：上游 [changelog](https://github.com/hukkin/tomli-w/blob/1210bb6f5708a4dc084cc3deb4a3a3e3939f4d6d/CHANGELOG.md) 记录 1.0 API/array formatting 和 1.1 Python support changes；0.2.2 起默认关闭 multiline strings，以避免 newline normalization。应固定 version/commit + package integrity，serializer 升级重新跑 native fixture，而非依赖 latest。

未安装或升级依赖。用 clone 的 `src` 作 `PYTHONPATH`，在现有 `ai-video-p2` 环境执行 upstream `tests/test_valid.py tests/test_invalid.py tests/test_style.py tests/test_types.py tests/test_write_file.py`：**268 passed, 2 xfailed, 0.20s**。两项 xfail 是上游声明不支持的极深递归 fixture；另对 newline/CR/普通文本/引号反斜线/control characters/中文六例 roundtrip 全通过。这些是 serializer evidence，不是 HM integration 或 native runtime qualification；没有运行 profiler test。

## Verification Implications

后续实现或评估至少需要下列 executable evidence，不能用 schema validation、generated file existence 或 fake receipt 单独代替：

1. **Resource fidelity**：fixture 同时含 UTF-8 text、binary bytes、nested scripts、executable mode、references；manifest hashes 与 materialized files逐项匹配，遭篡改时 fail closed。
2. **Native projection**：对同一 canonical input 分别执行 Codex、Claude、Gemini 的 local/fake-native conformance；检查真实 discovery path、native parser、unsupported field diagnostic 与 `AGENTS.md` owner collision。没有实际 CLI/native loader 的测试只证明 renderer 文本。
3. **Lifecycle**：fake child 覆盖 stdout/stderr backpressure、timeout、SIGTERM/SIGKILL escalation、cancel race、non-zero exit、secret redaction、process-tree cleanup 和 receipt idempotency。
4. **Authority**：recovery 只能生成建议或进入 parent review；它不得 silently switch provider、fallback、activate artifacts 或把 project Harness PASS 写成 executor receipt。

## Evidence Limits

除了上节明确记录的 emitter probes 和 Tomli-W tests，其余 upstream suites 均未运行；没有完成 transitive dependency audit、native adapter activation 或真实 Provider 验证。上游 test files 只能说明覆盖意图；`v2.1.0`、release、star 数、当前 open issues 与一份 `gemini-extension.json` 都不能证明当前 host 的 native activation。任何实际复用都应固定 SHA/package integrity 与 license notice，并取得与所用 capability 相符的 evidence。
