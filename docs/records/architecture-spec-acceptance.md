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
