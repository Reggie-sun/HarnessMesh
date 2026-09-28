# Implementation Status

## Approved Image API Candidate — 2026-09-29

用户“批准”接受Codex api-bounded amendment，已实现固定OpenAI Responses TLS broker、sealed generation cap映射、独立private credential、image-only Docker执行/终态/receipts、owned probe与一次性host预算门。Fresh offline524 PASS/27 skip，完整native/fake+containment548 PASS/3 skip，ruff/diffcheck通过；两新route只取得工程证据。

Required Kimi deep/max review第一轮invocation `5d46f112-ba0e-48ae-afa0-10b2b1640d9a` 在第二次请求TLS CONNECT失败，canonical OUTCOME_UNKNOWN，无完整报告；没有补请求或采用部分结果。accepted Spec禁止缺有效review安装，故本任务未安装candidate，旧安装current source为223da83（由其他任务维护，dirty_at_install=true）。真实visual probe/formal均0，缺独立OpenAI credential/current额度/accounting，capability及M5-D2A INCOMPLETE，生产BLOCKED。下面bba安装及待批准描述为历史状态。完整证据、事故恢复、Risk Gate及剩余工作见 [API record](records/image-api-engineering-2026-09-29.md)。

## Kimi Maximum Project Resources — 2026-09-29

按用户选择 C，新 Kimi project task 在 inspect/seal 前应用 `kimi-maximum-v1`：deep/max/1M 与当前最高有限资源；原请求和有效 route/预算均明示，旧 seal 不改写。Focused 131 PASS；完整 offline 376 PASS/25 skip/42 socket-permission failures，未声称完整/native/live 验证通过。受管 Kimi mapping 因 Docker preflight blocked，无 Provider request。安装状态、source hashes、Risk Gate 与不变的历史 review 预算见 [record](records/kimi-maximum-resources-2026-09-29.md)。

## Generation Budget Investigation — 2026-09-29

用户要求先修复blocker再安装。实际 Codex 0.154.0 请求、RPC schema及同版本官方源码没有已证明的≤2048 hard generation setter；本轮 native/fake 否定门测试1 PASS，证明拒绝有效，不证明视觉路线已修复。已准备新增明确 OpenAI API计费profile的窄修订，Self-Review完成、新exact SHA待用户批准；未改变旧accepted bytes或安装。受管Kimi安装边界mapping第二个请求TLS失败，canonical OUTCOME_UNKNOWN保留、无重试、未采用报告。新视觉/formal请求仍0，完整执行与qualification仍INCOMPLETE。当前installed source仍bba0563；其他任务的source/budget dirty保持。诊断、具体批准边界、安装核验和13项证据见 [record](records/generation-budget-blocker-2026-09-29.md)。

## Image Input Engineering — 2026-09-29

用户“那继续实现啊”已批准 image supplement 的已展示 exact SHA，进入实施；上一节批准待定为历史状态。独立 image contract/seal、source CLI `inspect-images`、Kimi native image projection/wire guard 与 Codex Docker diagnostic input 已实际实施。Fresh offline 397 PASS/25 skip，显式 native/fake+containment 420 PASS/2 skip，ruff 与 diff check 通过；这些只证明工程输入边界。

Codex 实际请求的工具列表和额外 instructions 已清空，但没有可证实的生成 token 上限；`IMAGE_GENERATION_BOUND_UNPROVEN` 阻断 live route。尚未实现 authenticated Codex broker/relay、完整 image execution/typed qualification owner；当前安装未替换，真实视觉 probe/formal requests 均为0，整体 INCOMPLETE。源码、具体控制项、Risk Gate、失败历史和剩余工作见 [record](records/image-input-engineering-2026-09-29.md)。

## Image Route Preparation and Reporting Repair — 2026-09-29

Jianji M5-D2A用户已授权router视觉扩展及受管安装。新增image contract已Self-Review，但新exact SHA待base V3批准，新image semantics尚未实施，visual capability NOT_EVALUATED。等待期间修复现有FINAL_REPORT工具响应阶段被diagnostic phase覆盖的缺陷；原JSON/SSE两个否定测试真实red，修复后offline315 PASS，native/fake+containment333 PASS/2 skip，explicit通用container另1 PASS。G2对该收紧拒绝条件的一行修复为KIMI_REVIEW_NOT_REQUIRED；不传播到未来credential/image边界。证据、安装及剩余门见 [record](records/image-route-blocker-repair-2026-09-29.md)。

## Timeout Follow-up — 2026-09-28

新证据表明，前次修复后单次长生成仍可耗尽 wall deadline。按用户选择，新 Kimi task 封存显式 generation_tokens（默认 4096），生成截断即拒收并 revoke、不自动续写；旧 seal 不静默改写。另新增 project 每次请求前的原 seal/source 校验及 `inspect.frozen_source_paths`，减少 source drift 后继续付费的浪费；未改变 final acceptance 或将超时宣称已根治。诊断、测试和边界见 [record](records/kimi-timeout-followup-2026-09-28.md)。

## Kimi Timeout And Reporting — 2026-09-27

Broker 的实际上游 headers/chunks 纳入 supervisor idle 判断，完整身份验证后交付与总 wall deadline 保持；项目请求新增有限的收尾阶段，剩余时间或最后请求触发停止工具探索并生成报告。源代码、安装、native/live 证据与限制见 [record](records/kimi-timeout-reporting-fix.md)。这不保证上游停滞或超大任务必然完成，不改写历史失败审查。

## Kimi Output Budget — 2026-09-27

修复项目调查反复以 report 大小设置 raw stream 预算的问题：Kimi task 缺省 output_bytes 在封存前填入 8 MiB，live project 小于 2 MiB 时零请求拒绝；显式 seal 不改写，16 MiB 硬上限与既有超限/证据规则保留。源码、受管安装和验证见 [record](records/kimi-output-budget-fix.md)。

## Entitlement Age Policy — 2026-09-26

按用户明确指令，Deep account entitlement observation 不再因超过 24 小时自动失效；历史观察日期保持原样。有效非未来时间戳、证据类型/来源、credential match、tier、1M entitlement 与 qualification 的依赖身份校验仍适用。该变化不证明远端当前订阅有效或已消费 1M context。离线验证和安装绑定见 [record](records/entitlement-age-limit-removal.md)。

## Authorization And Baseline

2026-09-19 用户明确要求“实现plan从M1到结束不要问我自己做决定”，授权实施本次读取的 M0 文档。原始文档只读冻结于 `baseline/`，其 PROPOSED 是历史状态；此处记录本轮 acceptance，不改写原始研究证据。

后续用户明确收敛为“先就把claude的搞好就可以，写一个文档记录好就可以”。当前交付为Claude Code/Kimi M1–M8；M9保留已有成果并暂停。

- Spec SHA-256: `46d17d008d64f2a4376bc58ecde866b81e9af4f70bdb3a9816d42680a11bdf39`
- Plan SHA-256: `64a65a21f4df88695f49d16b1073b8193c1f685332b049dbae6ac590e55caf35`
- Source owner: 本独立 local Git repo。无 remote、push、release、worktree。

## Scope And Ownership

Parent 拥有准入、source/receipt核验、parent acceptance、安装与最终验证。Native bounded workers按互不交叠的文件集合实施 resolver、Docker containment、candidate lifecycle 和 Gemini adapter；独立 reviewer_max复核关键边界。旧MiniMax runner/global configs保持不变。Codegraph/tool_search不可用；使用exact source与执行探针。

## Qualification Ledger

| Milestone | Current evidence |
| --- | --- |
| M1a | LIVE_ROUTE_VERIFIED。worker/deep精确model/thinking/effort均获authenticated upstream identity；deep初次403保留，显式correction通过。当前CC Switch同一key绑定于新qualification receipts |
| M1b | CONTAINMENT_VERIFIED。bwrap仍失败；改用现有Docker普通非特权容器，20项OS负向探针及真实Claude native工具边界通过；无host policy/sysctl改动 |
| M2 | IMPLEMENTED。typed contracts、stdin、双流排空、process group、cancel/timeout、有限输出、原子receipt与recovery unknown |
| M3 | IMPLEMENTED。exact source closure、祖先/nested rules、完整Skill assets、显式active refs/Harness与hash/mode drift |
| M4 | NATIVE_CONFORMANT。Claude2.1.277 native projection，Read/Glob/Grep限定/work，Bash/Task/Agent/MCP拒绝，Unix socket broker |
| M5 | VERIFIED_BOUNDARY。live identity、secret隔离、credential fingerprint与canonical qualification ID绑定；错route/缺identity/超预算/篡改拒绝 |
| M6 | LIVE_QUALIFIED。sealed project invocation、实际Read内容/range校验、严格report协议、独立无key/network parent测试域通过 |
| M7 | QUALIFIED。8 matched live任务均通过parent冻结rubric（unsupported claims单独记录），jizhang 92 tests和lint通过；10 synthetic corpus通过，历史10案仍UNRESOLVED_PROVENANCE |
| M8 | LIVE_QUALIFIED_SINGLE_FILE。真实Kimi候选经strict report、sealed candidate test、parent原子应用与实际bytes核验；重复tool ID回归应用后通过。初次report失败保留，独立一次prompt correction通过 |
| M9 | PAUSED_BY_USER / PARTIAL。Gemini0.60.0独立runtime、OAuth/CodeAssist broker、native GEMINI.md、Read/Glob/list、隔离与fake conformance通过；现有账号UNSUPPORTED_CLIENT，无generation，两repo live未完成。selected Skills明确拒绝，未宣称native Skill资格 |

## Proof Boundaries

Deep账号Pro membership由parent只读观察现有已登录Kimi console，key掩码与本地credential匹配；官方Pro支持1M。configured window、account entitlement与实际1M context consumption分开，后者NOT_EVALUATED。历史smoke未改写；后续qualification新receipt绑定当前key及account artifact。其证明边界不扩大到provider-wide性能或可靠性。

Docker worker非root、read-only root/source、无network/host HOME/daemon socket、drop-all capabilities、seccomp/AppArmor/NNP；parent-owned broker独占真实key。模型输出不产生parent acceptance。SIGKILL/daemon不可用时的orphan recovery仍未完整验收。

## Evidence And Acceptance

当前本机恢复证据见[resume-qualification.md](records/resume-qualification.md)。此前离线实现与旧安装记录保留于[implementation-checkpoint.md](records/implementation-checkpoint.md)，其中blocked状态为历史记录。

完整结果、failed attempts、review与安装绑定见[final-qualification.md](records/final-qualification.md)。M9外部资格未解决，不能宣称M1–M9全部完成。CLI/Skill均提供实际功能与typed blocker，不借文档状态绕过准入。
