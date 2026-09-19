# Implementation Status

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
