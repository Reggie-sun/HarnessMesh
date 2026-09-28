# HarnessMesh Architecture Spec Acceptance

## Status

`ACCEPTED_SPEC_WITH_USER_DIRECTED_Q2_AMENDMENT`

2026-09-26 用户在获知本地 Deep entitlement 的 24 小时自动过期规则后，明确要求“开子代理把这个路由策略去掉不要有限制”。当前 Q2 据此作一处窄修订：取消 observation age 的上限，保留有效非未来时间戳、account/credential/context 证明和依赖失效条件。此次执行授权直接来自当前指令；不伪称用户重新逐字批准了整份 Spec 的新 SHA。修订后的 SHA-256 为 `a3c216c077608767e1ac7ac7d03869e8d90f49256469691e8206c71edbf3566c`，实施证据见 [entitlement-age-limit-removal.md](entitlement-age-limit-removal.md)。

用户在收到新 written Spec 的 exact path 与 SHA-256 后，于 2026-09-23 明确答复“批准”。该历史批准只绑定下列 exact bytes，不覆盖上方修订；上方修订依赖另行明确的用户变更指令。其余未来 semantic revision 仍按 Spec 的 `V3` 与 `G1` 执行。

## Original Accepted Artifact

- Canonical Spec path: `docs/superpowers/specs/2026-09-23-harnessmesh-rare-review-design.md`
- SHA-256: `ff18503d3099f16d18947cc56a983b942aed6567dd61573beed24a3634fe8d5c`
- Source commit: `67da77c32330cede94147aec7176ec26cb0fa6db`
- Source tree: `5070d8f2f279156e6f2721f528be0526573caa03`
- User approval recorded at: `2026-09-23T21:47:34+08:00`

## Previous Accepted Snapshot

旧版 `docs/superpowers/specs/2026-09-19-harnessmesh-architecture-design.md` 的 SHA-256 为 `9f732140424db3a96772f115ec0ff2ef212b525822d6593de95be561777f6203`，用户批准记录时间为 `2026-09-23T20:21:50+08:00`。旧版 bytes 保留为历史证据；本次批准后不再是当前 canonical Spec。

## Acceptance Boundary

本次 acceptance 只确认上述 exact Spec snapshot 已通过 `superpowers:brainstorming` Architectural flow、Spec Self-Review 与 User Review Gate。Spec 内的 “draft”/“user review pending” 是批准前封存 bytes 中的历史 metadata；当前 acceptance 状态以本记录绑定的 path、SHA-256 与用户批准为准。依照该 Spec 的 `G1`，Spec 默认不调用 Kimi review；未执行 Kimi Spec review 不是缺失 gate。

本记录不接受或声称任何 Implementation Plan、runtime implementation、refactor、push 或 release，也不把 Spec acceptance 解释为 implementation completion、qualification 或 project-native verification PASS。

## Accepted Image Route Supplement

2026-09-29 用户先明确选择“包含 router 扩展，保留 sealed contract、Docker 和资格门”，随后在获知 image-only route written Spec 的 exact path/SHA 和尚未实施状态后要求“那继续实现啊”。该指令批准并授权执行已展示的下列 supplement；不是此前已实施或 qualified 的证明。

- Path: `docs/superpowers/specs/2026-09-29-image-only-route-design.md`
- SHA-256: `c1169a61ba8573a2c4ce442b321683a65b800230d3e8620e069e388a6d97c0f1`
- Approval source: 当前用户继续实施指令，绑定上述前一窗口已展示的 unchanged bytes。
- Base contract: 上述 current accepted architecture Spec；新 mode 不放宽旧 project worker schema、工具或 authority。

Supplement 内 `DRAFT / EXACT_SHA_APPROVAL_PENDING` 是批准前 frozen bytes 的历史 metadata；当前批准由本记录独占绑定。授权包括 implementation planning、受限实现、native/fake/containment 验证与符合冻结条件的最多两次独立 capability probes。它不批准无限商业调用、正式 Jianji semantic qualification 的未冻结预算或产品 activation。

## Accepted Codex Image API Amendment

2026-09-29 用户在收到新API修订路径、exact SHA及新增计费边界后明确回复“批准”，按前一回复推荐A批准实施及受管安装。绑定 `docs/superpowers/specs/2026-09-29-codex-image-api-budget-design.md` SHA `14e10cad0f3afc44f0f3796c2ae86c45e161c8a17ab2d54801c8c261a81df272`；原frozen文件的DRAFT/approval pending为历史metadata，bytes不变。本窄修订明确覆盖image supplement的Codex subscription transport为新增 `api-bounded` profile/fixed OpenAI Responses API/API Key与单字段generation cap映射；旧profiles不自动迁移。

新增OpenAI capability probe最多一次、费用上限USD1，并须原spec所有native/OS/真实credential、actual payload、cost upper bound与已授权account额度证据成立；Kimi仍最多一次，两条合计最多两次，不retry/fallback。正式holdout cost authorization=0，production授权未扩大。该批准接受Spec并授权范围内implementation planning/execution/verification/review/installation，不证明代码已完成、live能力或source semantic资格。

## User Directed Engineering Review Fallback

2026-09-29 用户明确要求“修改逻辑,当kimi一直出问题的时候得用原生子代理”。该新授权仅修订 base §9 及 API amendment 的 engineering reviewer 限制：连续两次真实受管 Kimi 运行故障无完整输出时，按照 `/home/reggie/.codex/SUBAGENTS.md` 的 Repeated Kimi Failure Fallback，由一个职责匹配的 read-only native Codex reviewer 接手同一候选审查，Parent 仍须核实全部 findings 与 verification。不是删除 required review，也不是声称用户事先批准本段的新 SHA；执行授权来自这条明确变更指令。

旧 accepted Spec bytes 与两次 OUTCOME_UNKNOWN receipts 保留原样。安全/权限/预算/资格拒绝、源码漂移或 reviewer 硬错误不能充当故障触发。Native 身份与执行证据独立记录，不伪称具有 Kimi Docker/route receipts；任何 semantic fix 仍须新 snapshot、验证及适用 re-review。当前两次 invocation `5d46f112-ba0e-48ae-afa0-10b2b1640d9a`、`dbd52980-2e47-4b06-9ff3-f6609a89a90f` 的 transport 故障满足本条阈值，下一步执行 native 工程审查而非第三次付费 Kimi 调用。

Image actor/provider、sealed contract、qualified route、Docker containment、canonical image receipts、有限 capability 费用及 formal budget=0 保持。安装仍需有效 required engineering review 与 Parent 裁决；本修订不批准生产、source admission、视觉资格或使用本聊天充当 blinded actor。
