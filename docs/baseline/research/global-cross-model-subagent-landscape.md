# Global Cross-Model Subagent Landscape

Date: 2026-09-19
Status: research complete for the bounded source audit; implementation/live qualification not started.

## Decision

建议建设**薄 supervisor + native runtime adapters + restricted credential/identity broker**，不安装六套framework的组合，也不让global router接管项目Harness。最接近的基础参考是 `shinpr/sub-agents-skills` 的小模块CLI abstraction；投影借鉴 `wshobson/agents` 和 `madebywild/agent-harness`；receipt/lifecycle借鉴AGPair。首阶段不引入CCR或CodeRouter作为routing dependency。

这是对当前source与本机constraints的选择，尚不是运行时性能结论。优先考虑复用经过审查的小模块/tests；实际复用代码量、license notices和dependency lock在implementation时记录。目前未vendor、fork或安装任何组件。

## Method And Evidence Levels

逐项clone当前default branch、固定HEAD，检查实现、tests、license及GitHub issues/releases/CI；不是README-only。两组独立native researchers使用`gpt-6-astra / ultra`，parent复读关键身份/权限/dirty-baseline缺陷源码。上游代码作为研究数据，不授予项目权限。

- `STATIC`：固定commit的源码观察。
- `OFFLINE`：本轮执行的pure/fake probe或tests，无live provider。
- `UPSTREAM REPORT`：上游issue/CI作者证据，未在本机复现。
- `LIVE`：本轮实际目标provider调用；**本轮为0**。

当前tool registry没有codegraph/tool_search；使用精确symbol/text/AST检查，不宣称做过codegraph indexing。Stats由GitHub repo API获取；open_issues_count包含PR，不等于缺陷数。许可证核对不等于完整dependency/security audit。

## Repository Snapshot

| Project | Stars / forks | Last push UTC | Pinned HEAD | License / release evidence |
| --- | ---: | --- | --- | --- |
| [musistudio/claude-code-router](https://github.com/musistudio/claude-code-router) | 37316 / 3135 | 2026-09-18 | `a034b0c51cdd1b5628bbff545821f5540d30c6c5` | MIT; core 3.1.1 |
| [wshobson/agents](https://github.com/wshobson/agents) | 39776 / 4241 | 2026-09-14 | `4236bb91f8395b0435f1d8b8baf9e8e4c69a8620` | MIT; actively maintained content/generator |
| [shinpr/sub-agents-skills](https://github.com/shinpr/sub-agents-skills) | 87 / 16 | 2026-09-06 | `84e1d4b311dd1f87b71687b62cb1d97744393b80` | MIT; 0.13.3 |
| [zephel01/CodeRouter](https://github.com/zephel01/CodeRouter) | 49 / 2 | 2026-08-21 | `65ae72059ad465cbd5d58f1e774708d35af52f67` | MIT; 2.15.0 |
| [logicrw/agpair](https://github.com/logicrw/agpair) | 48 / 0 | 2026-06-29 | `755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98` | MIT; no releases found |
| [madebywild/agent-harness](https://github.com/madebywild/agent-harness) | 13 / 0 | 2026-09-01 | `2ecf44f97ab6ffd76f5c1a58ac57b930e2ccfa17` | MIT; v2.1.0 |
| [zephel01/coderouter-plugin-agents](https://github.com/zephel01/coderouter-plugin-agents) | 0 / 0 | 2026-07-11 | `b5797fd8457337831827b4322200b50d019e008a` | MIT; 0.1.0 |
| [Code-Router/CodeRouter](https://github.com/Code-Router/CodeRouter) | 2 / 1 | 2026-07-11 | `3cb23b8a292f399a86f861742c9d77a59a9f23b5` | MIT; distinct project |

所有上述repo查询时未archived。API原始非敏感metadata封存于 [upstream-metadata.json](upstream-metadata.json)。Stars不作为选择依据。Source checkout缓存为 `/tmp/agent-router-research-20260919-emh1xeij/`；最终证据使用pinned upstream links，不依赖临时目录永久存在。

## Capability Comparison

| Project | Architecture / transport | Runtimes / models actually represented | Harness / identity / receipt |
| --- | --- | --- | --- |
| CCR | HTTP multi-protocol gateway，routing policies，upstream attempts，optional translation | Claude host；另有Codex patch/protocol bridge；OpenAI/Anthropic/Gemini协议；模型由provider registry配置，无本轮live qualification | 不解析project Harness；requested/resolved/response trace，但downstream model可被改写 |
| wshobson | canonical content → per-runtime files | Claude-native内容；Codex/Copilot/Cursor/OpenCode/Antigravity/Pi generators；无独立Gemini CLI adapter；存在静态模型别名映射 | 内容投影和drift；不执行provider，也无运行身份receipt |
| shinpr | role definition → immutable invocation → CLI subprocess → stream parser | Codex/Claude/Cursor/Grok/Gemini/Antigravity/OpenCode/Command Code；Kimi/GLM经Claude；model opaque；upstream无正式MiniMax分支，本机fork有 | 角色prompt+CLI flags；非project resolver；最终envelope丢弃identity/usage |
| CodeRouter+plugin | API gateway → provider/plugin → one-shot CLI | Claude/Codex/Grok/Antigravity；Gemini明确拒绝；Kimi可通过env手动接但无专有profile/验证 | fallback trace、session/usage；project cwd需配置；response.model来自config |
| AGPair | controller task/attempt/session → external executor → receipt/recovery | Codex/Claude及其executor registry中的外部runtime；Gemini被当前policy拒绝；模型选择由executor配置 | durable state/artifacts/receipt；controller accept显式，但非project-native verification执行器；无充分observed-model保证 |
| agent-harness | canonical `.harness/src` → loader/adapter/planner/apply | Codex/Claude/Copilot/Cursor；model为provider override，无runtime model调用 | 强配置ownership/drift；不是执行Harness，不提供调用identity/receipt |

以上是源码分支或生成物支持，不等于对每个模型和当前CLI版本的E2E验收。

## A — Claude Code Router

### Architecture And Reuse

当前是v3.1.1，不应沿用v2事故当当前代码。`claude-code-router-plugin` 按custom router、subagent tag、profile/global rules、env/client/builtin/default顺序选route。完整上游兼容还依赖 `@the-next-ai/ai-gateway ^1.0.21`，Node >=22、SQLite/HTTP依赖扩大维护面。[routing pipeline](https://github.com/musistudio/claude-code-router/blob/a034b0c51cdd1b5628bbff545821f5540d30c6c5/packages/core/src/gateway/claude-code-router-plugin.ts#L62-L135)、[precedence](https://github.com/musistudio/claude-code-router/blob/a034b0c51cdd1b5628bbff545821f5540d30c6c5/packages/core/src/gateway/claude-code-router-plugin.ts#L292-L418)、[package](https://github.com/musistudio/claude-code-router/blob/a034b0c51cdd1b5628bbff545821f5540d30c6c5/packages/core/package.json)

可借鉴：明确protocol boundary、UTF-8/SSE chunk处理、attempt trace、requested/resolved/observed分列。`codex-patch-bridge` 将Codex custom `apply_patch` 转为`virtual_apply_patch`函数，并处理history及response；不是仅改tool名称。[bridge](https://github.com/musistudio/claude-code-router/blob/a034b0c51cdd1b5628bbff545821f5540d30c6c5/packages/core/src/gateway/features/codex-patch-bridge.ts#L178-L399)

Claude-only部分是subagent tag注入/提取与Claude model tiers。Codex oriented层可借鉴API协议适配与观测，但本任务让Kimi使用Claude native tools，首阶段不需要重做Codex apply_patch翻译；模型名称含`gpt`的heuristic也不是capability证明。

### Silent Routing History And Current Behavior

[#1564](https://github.com/musistudio/claude-code-router/issues/1564) 报告v2.0仅检查`system[1]`，实际tag在`system[2]`，所有子任务仍成功却走default模型；模型读到tag又自报不同身份。事故细节为UPSTREAM REPORT，未本机重演。

当前代码已扫描全部system blocks与前两条user messages；但未解析/未配置的tag仍会继续其他routing，位于更后message的tag被忽略，测试期望default。[current extraction](https://github.com/musistudio/claude-code-router/blob/a034b0c51cdd1b5628bbff545821f5540d30c6c5/packages/core/src/gateway/claude-code-router-plugin.ts#L1106-L1216)、[unknown target](https://github.com/musistudio/claude-code-router/blob/a034b0c51cdd1b5628bbff545821f5540d30c6c5/packages/core/src/gateway/claude-code-router-plugin.ts#L474-L497)、[test](https://github.com/musistudio/claude-code-router/blob/a034b0c51cdd1b5628bbff545821f5540d30c6c5/packages/core/test/unit/gateway/router-builtins.test.mjs#L3018-L3070)

最重要的STATIC事实：当前会将Anthropic SSE `message_start.message.model` 改为client-visible requested model。[rewrite](https://github.com/musistudio/claude-code-router/blob/a034b0c51cdd1b5628bbff545821f5540d30c6c5/packages/core/src/gateway/features/anthropic-response-model.ts#L74-L93) Parent已复读确认。仅看gateway下游JSON/SSE仍可能误报identity。SQLite有三种model列，但部分字段有fallback attribution，要同时保留来源。[log attribution](https://github.com/musistudio/claude-code-router/blob/a034b0c51cdd1b5628bbff545821f5540d30c6c5/packages/core/src/observability/request-log-store.ts#L600-L636)

### Failure, Security And Verdict

Retry/model chains、credential attempts、fallback headers增加透明度，但有记录的自动fallback仍不满足本任务。自定义JS router加载和request body logs也不是默认需要的安全面。[upstream attempts](https://github.com/musistudio/claude-code-router/blob/a034b0c51cdd1b5628bbff545821f5540d30c6c5/packages/core/src/gateway/upstream/executor.ts#L471-L568)

源码有patch bridge和fallback unit tests，本轮未运行CCR build/suite。维护活跃、issue #1564具备具体复现价值；不能据此证明所有当前协议都可用。**不直接依赖CCR core；借鉴测试与attribution设计。** 如未来引入必须关闭routing/fallback及identity改写，并从upstream取证。不能以一层薄prompt adapter掩盖这些contract冲突。

## B — wshobson/agents

Canonical内容在`plugins/*/{agents,skills,commands}`，各adapter输出native artifacts；Codex adapter特意不生成root AGENTS，保留项目owner。当前generator列出Codex/Copilot/Cursor/OpenCode/Antigravity/Pi，而不是所有名称均等价支持。[owner boundary](https://github.com/wshobson/agents/blob/4236bb91f8395b0435f1d8b8baf9e8e4c69a8620/tools/adapters/codex.py#L1-L13)、[registry](https://github.com/wshobson/agents/blob/4236bb91f8395b0435f1d8b8baf9e8e4c69a8620/tools/generate.py#L35-L70)

值得保留native差异：Codex agent TOML、namespaced Skills、Claude commands转Skills、Cursor依自身discovery。CI regenerate+Git diff比“请保持同步”更可执行。[CI](https://github.com/wshobson/agents/blob/4236bb91f8395b0435f1d8b8baf9e8e4c69a8620/.github/workflows/validate.yml#L183-L205)

不能照搬：

- `inherit`映射到固定`gpt-5.5`，会偷换parent model策略。[mapping](https://github.com/wshobson/agents/blob/4236bb91f8395b0435f1d8b8baf9e8e4c69a8620/tools/adapters/capabilities.py#L302-L319)
- 工具allowlist降为粗粒度sandbox；缺tools可推到workspace-write，不是权限等价转换。[projection](https://github.com/wshobson/agents/blob/4236bb91f8395b0435f1d8b8baf9e8e4c69a8620/tools/adapters/codex.py#L409-L433)
- `_emit_skill`仅复制SKILL.md/references，实际pptx skill有3个scripts，内存probe生成0个；因此不能称完整bundle投影。[implementation](https://github.com/wshobson/agents/blob/4236bb91f8395b0435f1d8b8baf9e8e4c69a8620/tools/adapters/codex.py#L361-L398)

Codex smoke主要doctor/TOML parse，未实际调用生成agent；当前[PR #711](https://github.com/wshobson/agents/pull/711)补YAML validity，尚未在pinned HEAD中。**借鉴canonical→native架构与drift tests，不安装整套catalog，不复用有损权限/model mapping。** 无provider transport、identity receipt或业务Harness，不应为它添加这些虚构能力。[smoke boundary](https://github.com/wshobson/agents/blob/4236bb91f8395b0435f1d8b8baf9e8e4c69a8620/tools/tests/test_cli_smoke.py#L264-L312)

## C — shinpr/sub-agents-skills

最接近所需：`AgentDefinition → AgentInvocation → ProcessInvocation → subprocess → StreamProcessor → AgentResponse`，Python标准库runtime、role与backend分开。Kimi/GLM通过Claude CLI，明确清理Anthropic两种auth env再注入选定credential；Kimi key不进入argv。其`.com`endpoint与当前官方推荐`.ai`不同，但未live验证，不能断言旧endpoint不可用。[builders](https://github.com/shinpr/sub-agents-skills/blob/84e1d4b311dd1f87b71687b62cb1d97744393b80/skills/sub-agents/scripts/_builder.py#L244-L348)

本轮176个focused tests PASS，另有两个OFFLINE缺陷probe：final envelope丢弃model/session/usage；fake child先输出1MiB stderr会在400ms超时，因只排stdout形成回压。[response](https://github.com/shinpr/sub-agents-skills/blob/84e1d4b311dd1f87b71687b62cb1d97744393b80/skills/sub-agents/scripts/_executor.py#L143-L163)、[drive](https://github.com/shinpr/sub-agents-skills/blob/84e1d4b311dd1f87b71687b62cb1d97744393b80/skills/sub-agents/scripts/_executor.py#L170-L259)

继承完整父环境、只杀直属进程、permission只映射CLI flags，无法直接证明secret/file/process isolation。脚本缺backend会fail closed，SKILL却建议缺run-agent时fallback当前客户端，形成控制面冲突。[spawn/env](https://github.com/shinpr/sub-agents-skills/blob/84e1d4b311dd1f87b71687b62cb1d97744393b80/skills/sub-agents/scripts/_executor.py#L283-L331)、[Skill fallback](https://github.com/shinpr/sub-agents-skills/blob/84e1d4b311dd1f87b71687b62cb1d97744393b80/skills/sub-agents/SKILL.md#L102-L106)

Kimi分支用`--system-prompt`替换原system context，普通Claude用append；必须明确是否保留native指导，不能默认相同。全局role registry易复用，但不具备自动project contract resolver。**优先评估builder/parser/test片段复用；不继承默认safe-edit、yolo、Skill fallback、envelope和process lifecycle。** MIT attribution必保留。低依赖值得肯定，但测试通过不涵盖上述反例。

## D — CodeRouter

这里主研究对象是`zephel01/CodeRouter`及独立`coderouter-plugin-agents`；另一个同名repo单列。Core提供Anthropic/OpenAI ingress与provider fallback，`agent_cli`必须装plugin，未启用会启动失败。Plugin执行完整CLI子任务，扁平化roles、丢弃非文本块，最终文本完成后再pseudo-stream；并非native tool-loop透传。[registry](https://github.com/zephel01/CodeRouter/blob/65ae72059ad465cbd5d58f1e774708d35af52f67/coderouter/adapters/registry.py#L18-L84)、[prompt rendering](https://github.com/zephel01/coderouter-plugin-agents/blob/b5797fd8457337831827b4322200b50d019e008a/src/coderouter_plugin_agents/adapter.py#L1060-L1089)

实际Claude/Codex/Grok/Antigravity分支存在；Gemini constructor拒绝。其文档/代码用停服理由解释，这与当前[Google官方authentication](https://geminicli.com/docs/get-started/authentication/)和[release记录](https://github.com/google-gemini/gemini-cli/releases)不符；只报告这个项目不支持Gemini，不扩展为官方停服事实。[adapter registry](https://github.com/zephel01/coderouter-plugin-agents/blob/b5797fd8457337831827b4322200b50d019e008a/src/coderouter_plugin_agents/adapter.py#L226-L277)

可借鉴：stdin传prompt、argv不shell、env白名单、timeout process group、typed schema、trace区分skip/attempt failure。不能照搬的E2E缺陷：

- 原方法体内存probe中CLI请求override model，response仍返回config model；Claude parser没有observed-model提取。[argv](https://github.com/zephel01/coderouter-plugin-agents/blob/b5797fd8457337831827b4322200b50d019e008a/src/coderouter_plugin_agents/adapter.py#L478-L484)、[response](https://github.com/zephel01/coderouter-plugin-agents/blob/b5797fd8457337831827b4322200b50d019e008a/src/coderouter_plugin_agents/adapter.py#L1040-L1057)
- fake subprocess cancel probe证明`generate`没有执行child cleanup；只处理TimeoutError不覆盖取消。[lifecycle](https://github.com/zephel01/coderouter-plugin-agents/blob/b5797fd8457337831827b4322200b50d019e008a/src/coderouter_plugin_agents/adapter.py#L392-L421)
- 非零exit均可retry，可能遮蔽授权/config失败或在有写效果后重复执行；HOME继承仍会带入hooks/MCP/config。[classifier](https://github.com/zephel01/coderouter-plugin-agents/blob/b5797fd8457337831827b4322200b50d019e008a/src/coderouter_plugin_agents/adapter.py#L1190-L1197)

Tests中的“E2E”实际fake subprocess；有argv/env/timeout framing价值，没有本机真实backend身份保证。[fake fixtures](https://github.com/zephel01/coderouter-plugin-agents/blob/b5797fd8457337831827b4322200b50d019e008a/tests/test_agent_cli.py#L1301-L1311) 本轮没有其MCP live integration或真实CLI session；debug JSONL/trace只是执行信息，不能证明精确model。Plugin还依赖Core `>=2.8,<3.0`、Python>=3.12，原样引入会带来不必要的gateway/fallback栈。**借鉴进程/env/trace，不直接依赖整个engine。**

## E — AGPair

AGPair确实比普通prompt wrapper更接近controller/worker生命周期：task/attempt持久化、stdout/stderr/artifacts、receipt dedup、recovery决策。`artifact_result`与`agent_result`分层尤其值得复用。[executor](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/agpair/executors/local_cli.py#L594-L775)、[recovery](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/agpair/recovery.py#L66-L110)、[dedup](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/agpair/storage/receipts.py#L31-L61)

controller的`task accept`是显式决定，但只检查phase并标记approved，不自动执行项目verification。因此可借鉴authority separation，不能把accept命令当Harness proof。[accept](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/agpair/cli/task.py#L2465-L2512)

高风险边界：

- Codex默认dangerously bypass approvals/sandbox；Claude默认bypassPermissions，prompt中的authorization profile不是执法。[Codex defaults](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/agpair/executors/codex.py#L9-L15)、[Claude defaults](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/agpair/executors/claude_code.py#L19-L23)
- scope validator从actual paths减去baseline dirty paths；纯函数probe证明已脏文件再被worker改动可被忽略。两holdout都dirty，不能复用此算法。[scope](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/agpair/scope_validation.py#L112-L138)
- worker提供artifact路径后host copy缺少source confinement；receipt task/attempt association需要controller强绑定，不能依赖worker值。[copy](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/agpair/artifacts.py#L31-L39)
- bundled external-first routing policy与本用户Codex主控策略不同；不安装其hooks/policy。[Skill](https://github.com/logicrw/agpair/blob/755d4b2e4d9a14871dc66d59ba6fd4bc4a3afa98/skills/Codex/SKILL.md#L8-L26)

有fake lifecycle tests和real smoke脚本，后者不是本轮已执行。pinned HEAD的[CI run](https://github.com/logicrw/agpair/actions/runs/28378573962) Python tests失败、companion成功；最近3次查询均failure，未获取具体测试根因。没有issue/release样本不代表无bug。**借鉴receipt/recovery，不直接fork其默认执行策略和dirty算法。** session id仅是AGPair session，不保证原生model resume。

## F — madebywild/agent-harness

`.harness/src` canonical entities经loader/adapter/planner生成native配置，managed index与lock追踪ownership。支持Codex/Claude/Copilot/Cursor，不支持Gemini；prompt sections可生成AGENTS/CLAUDE，这对已有canonical项目不能直接启用。[schema](https://github.com/madebywild/agent-harness/blob/2ecf44f97ab6ffd76f5c1a58ac57b930e2ccfa17/packages/manifest-schema/src/index.ts#L14-L27)、[composition](https://github.com/madebywild/agent-harness/blob/2ecf44f97ab6ffd76f5c1a58ac57b930e2ccfa17/packages/toolkit/src/provider-adapters/create-adapter.ts#L36-L55)

值得复用的严格性：unmanaged collision拒绝、create/update/delete/noop plan、required hook不支持时报错；provider overrides保留native model/skills/MCP/sandbox差异。[planner](https://github.com/madebywild/agent-harness/blob/2ecf44f97ab6ffd76f5c1a58ac57b930e2ccfa17/packages/toolkit/src/planner.ts#L208-L310)、[hooks](https://github.com/madebywild/agent-harness/blob/2ecf44f97ab6ffd76f5c1a58ac57b930e2ccfa17/packages/toolkit/src/provider-adapters/hooks.ts#L426-L433)

不能照搬：loader把skill所有files按UTF-8读取，apply按UTF-8写回，binary assets/modes不能保证保真；apply依次写删后更新lock，不是多文件事务。其e2e运行自己的CLI，不是Codex/Claude实际加载。[loader](https://github.com/madebywild/agent-harness/blob/2ecf44f97ab6ffd76f5c1a58ac57b930e2ccfa17/packages/toolkit/src/loader.ts#L528-L548)、[apply](https://github.com/madebywild/agent-harness/blob/2ecf44f97ab6ffd76f5c1a58ac57b930e2ccfa17/packages/toolkit/src/engine.ts#L542-L571)

有[v2.1.0发布](https://github.com/madebywild/agent-harness/releases/tag/v2.1.0)及成功scheduled workflow；[v2.0.0](https://github.com/madebywild/agent-harness/releases/tag/v2.0.0)包含registry/prompt-section breaking refactor，需pin/version migration。**借鉴planner/ownership/drift，不把项目AGENTS纳入global managed output，不直接复用UTF-8 asset copier。**

## Updated Or Alternative Implementations

`Code-Router/CodeRouter`是另一个TypeScript CLI/Electron orchestrator，有自己的planning/judge/worktree flow。Codex adapter只在检测到API-key auth时传model，Claude adapter以worktree为理由bypass权限；均不符合本任务。Worktree不是sandbox，且用户未授权创建worktree。[Codex model](https://github.com/Code-Router/CodeRouter/blob/3cb23b8a292f399a86f861742c9d77a59a9f23b5/packages/core/src/adapters/codex.ts#L127-L134)、[Claude bypass](https://github.com/Code-Router/CodeRouter/blob/3cb23b8a292f399a86f861742c9d77a59a9f23b5/packages/core/src/adapters/claudeCode.ts#L20-L30)

本机Reggie-skill fork已增加MiniMax、exact grants、dialogue/evidence guard，不能拿上游C的旧行为覆盖它的当前实现；见 [local inventory](local-state-inventory.md) 与 [regression catalog](minimax-regression-corpus.md)。不直接移植其过重model-owned状态协议。

补充调查 [anthropics/sandbox-runtime](https://github.com/anthropics/sandbox-runtime)，clone HEAD `5e436d328684f6c70e3a94aaf8b7627135bbaada`，package `0.0.76`，Apache-2.0。已查`package.json`、license、Linux实现：使用bwrap/net namespace、socat bridges与seccomp，包含capability probe和weaker mode。[Linux source](https://github.com/anthropics/sandbox-runtime/blob/5e436d328684f6c70e3a94aaf8b7627135bbaada/src/sandbox/linux-sandbox-utils.ts#L1125-L1173) 它可避免自写sandbox，但不是新的项目Harness，也不能让本机uid-map失败消失。本轮未运行其suite或完整dependency audit，安装与security qualification留给M1；不自动开启weaker mode。

## Kimi Official Contract

当前官方Claude集成使用 `https://api.kimi.ai/coding/`，worker `k3-256k/high`，deep客户端`k3[1m]`而wire是`k3`。`max`是K3有效effort，thinking关闭会转由K2.8；`kimi-for-coding`不能当K3身份。全部model tier aliases都应固定。1M权益取决于计划，不能从“已购买”推定。[official integration](https://www.kimi.com/code/docs/en/third-party-tools/claude-code.html)、[models](https://www.kimi.com/code/docs/en/kimi-code/models.html)

官方`/status`检查证明endpoint配置，有可能仍显示Claude名字；本任务要求更强的upstream request/response identity。Remote真实权重不可从客户端密码学认证，必须诚实界定证据层级。当前已安装Claude版本也必须做实际conformance，不能直接照抄最新指南并覆盖现有MiniMax全局配置。

## Verification Performed

| Probe | Result | Does not prove |
| --- | --- | --- |
| C builder/stream/final-response existing tests | 176 PASS | 全部CLI/provider E2E |
| C fake stderr + terminal | 124 timeout，复现回压 | Claude真实网络timeout |
| C response metadata probe | model/session/usage丢失 | 所有fork均同样丢失 |
| D original-method fake probes | override model错标；cancel不kill child | 真实provider已产生孤儿进程 |
| B in-memory skill emission | 3源scripts，0生成scripts | 所有安装路径都缺scripts |
| E pure dirty-baseline probe | 二次修改可能忽略 | host已发生数据损坏 |
| Local runner dialogue tests | 28 PASS | 新router或Kimi通过 |
| Host bwrap namespace probe | FAIL permission denied | 所有可选sandbox永不可用 |

C测试精确命令（researcher运行，clone最终clean）：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m pytest -q -p no:cacheprovider tests/test_builder.py \
  tests/test_stream.py tests/test_executor.py::TestBuildFinalResponse
```

其他probes是内存执行原函数/AST与fake process，无paid calls。Parent额外核对CCR model rewrite、D response model来源、E dirty算法、F UTF-8 copier。完整CCR/D/E/F suites与dependency vulnerability scan未执行，不声称通过。未clone执行任何上游install/postinstall scripts。

## Reuse And Rejection Summary

| Component | Decision | Reason |
| --- | --- | --- |
| C immutable invocation / builder/parser tests | 首选逐模块复用评估 | 最小、接近现有需求；补transport/identity/permission缺口 |
| B native projection architecture | 借鉴设计和测试思路 | 保留native能力；修正asset/permission/model损失 |
| F managed ownership / drift plan | 借鉴设计 | 防覆盖/漂移；不成为项目constitution新owner |
| E structured receipts / recovery | 借鉴分层 | 有价值的controller边界；拒绝bypass/dirty-path漏洞 |
| CCR full gateway | 首阶段拒绝依赖 | route precedence/fallback/model rewrite/日志面超出需要 |
| D full gateway/plugin | 首阶段拒绝依赖 | 第二套routing/fallback；identity与cancel缺陷 |
| Same-name Code-Router | 排除 | 独立primary orchestration、model选择不可靠、权限误判 |
| sandbox-runtime / bwrap | 条件复用 | 成熟OS primitive优于自写；必须先过本机capability与negative tests |

未发现某一项目能原样同时满足project contract resolver、强权限隔离、upstream identity、可信receipts和parent-only acceptance。薄组合仍需实现少量自有glue；应以M1尽早实测关键能力，避免先写庞大framework。

## Next Backend Recommendation

选择Gemini native CLI作为M9优先候选：它能验证不同wire、native instructions/skills/tools的适配，而GLM仅能验证Claude transport下第二provider。Google当前官方登录文档与近期release可核实；最终资格仍取决于其当前版本identity/permissions、用户本地credential与实际有界E2E。Grok需先确定official/community发行包，不能只写`grok`就宣称已验证。[Google auth](https://geminicli.com/docs/get-started/authentication/)、[configuration](https://geminicli.com/docs/reference/configuration/)
