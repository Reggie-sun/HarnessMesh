# Current Architecture Truth

Date: 2026-09-19. Status: research input; **not an accepted Architecture Spec**.

## Scope And Snapshot

本轮只做 research、architecture exploration、Spec authoring 与独立审查；不修改 runtime implementation，不写 implementation plan，不 refactor，不 push/release。正式 Spec 由当前安装的 `superpowers:brainstorming` Architectural path 负责，设计批准后才写入其规定路径。历史 baseline 是设计输入，其存在不构成本轮 approval。

检查起点：`main`，HEAD `a4d4c4e9c28346a92e4102b6c2fe393b4487bec4`，tree `b55fbcf3358177589ebcf941a94c5dacc011fd2f`，working tree clean，local tracking ref `origin/main` 与 HEAD 相同。没有为本轮创建 worktree。后续 research 文档不改变该源码检查点。

已检查 `AGENTS.md`、`README.md`、`pyproject.toml`、`docs/baseline/`、`docs/implementation-status.md`、`docs/records/`、`src/`、`tests/`、`skills/`、`scripts/` 的目录与相关内容，以及最近八个 commits。源码重点包括 API/resolver/projection/brokers/identity/protocol/receipts/qualification/supervisor/writer/apply；没有将目录盘点冒充每行安全审计。当前 callable tool registry 无 `codegraph` 或 `tool_search`，未进行 codegraph indexing；依据源码、symbol 搜索、测试和本机 receipts。

| Input owner | Exact bytes |
| --- | --- |
| Installed `superpowers:brainstorming` | `/home/reggie/.agents/skills/superpowers/brainstorming/SKILL.md`; SHA-256 `25a86367f3500415924243cc7f890764b006718ba58c21cc9f432c5bc024f6b2` |
| Installed `superpowers:writing-plans` | `/home/reggie/.agents/skills/superpowers/writing-plans/SKILL.md`; SHA-256 `6c682d7a116bf7983bdec0729dbaf2e82fadff446ab5d597302f1edfed3a6c92`; read only, not invoked |
| Earlier baseline Spec | `docs/baseline/specs/global-external-subagent-infrastructure.md`; SHA-256 `46d17d008d64f2a4376bc58ecde866b81e9af4f70bdb3a9816d42680a11bdf39` |
| Earlier baseline Plan | `docs/baseline/plans/global-external-subagent-implementation.md`; SHA-256 `64a65a21f4df88695f49d16b1073b8193c1f685332b049dbae6ac590e55caf35`; historical input only |

Installed skills resolve under `/home/reggie/.codex/superpowers/skills/`. Installed bytes, not a remembered upstream workflow, govern this round. Architectural path requires context, one-at-a-time meaningful clarification, 2–3 approaches, sectioned design approval, written Spec, Spec Self-Review and written-spec User Review Gate. The requested dual independent review is inserted after self-review and before final user approval. It does not remove earlier design approval.

## Implemented Surface

| Surface | Current owner and behavior | Evidence boundary |
| --- | --- | --- |
| Parent entry and admission | `api.py`, `contracts.py`, `cli.py`: explicit backend/profile, sealed route/runtime/image, bounded role/permissions, typed rejection | Parent still owns project truth; CLI exit 0 maps `PARSED`, not KEEP |
| Project Contract Resolver | `resolver/__init__.py`: root/source closure, instruction observations, parent-selected accepted refs, explicit Harness/Skills, source bytes/modes/hash seal and revalidation | Does not infer acceptance from filenames; does not semantically resolve every linked document or every runtime's constitution |
| Claude-native projection | `adapters/projection.py`, `adapters/project_claude.py`: selected original files, `.claude/rules/router-constitution.md`, complete selected Skill assets and executable bit, source map | Native Read/denials tested; semantic instruction precedence is not proved by presence of text alone |
| Kimi routing | `backends/kimi.py`, `transport/broker.py`, `transport/identity.py`: fixed authenticated endpoint, request model/thinking/effort checks, response identity/request association before delivery | Upstream declaration proof, not remote weight attestation; no silent fallback |
| Credentials | `transport/credentials.py`: provider-specific private reference; parent broker injects real key; runtime receives ephemeral capability | Capability is also secret. Filename exclusion/redaction are defense layers, not proof that arbitrary selected document bytes contain no secret |
| Process lifecycle | `supervisor.py`, `permissions/docker.py`: shell-free argv, isolated env, concurrent stdout/stderr drainage, finite budgets, stop/revoke/kill cleanup | Parent/Docker trusted; SIGKILL/daemon-loss orphan recovery not fully qualified |
| Receipt storage | `receipts.py`: supervisor-owned filtered artifacts, atomic publication, association/hash checks, durable last observations, unknown recovery | Local trusted-owner integrity; not a signature against a malicious host owner and not project acceptance |
| Route qualification | `route_qualification.py`, `project_run.verify_smoke`: runtime/profile/smoke/account/fingerprint bindings; deep account evidence freshness checked at invocation | Route-only eligibility; source smoke historically lacks its own credential fingerprint, explicitly documented in qualification record |
| Read-only qualification | `holdout_qualification.py`: exact eight-task runset, parent assessments, paired profiles and project gates | Frozen experiment scope; unsupported model claims remain possible |
| Candidate lifecycle | `writer_run.py`, `writer.py`, `candidate_gates.py`, `atomic_apply.py`: private candidate, immutable seal, parent-controlled contained test, explicit application/readback | Linux single-file existing clean tracked target; no new/delete/rename/mode/multifile transaction guarantee |
| Gemini | `adapters/gemini.py`, `gemini_run.py`, `transport/gemini_*`: separate native CLI/context, OAuth/Code Assist boundary and model response observation | Native/fake works; live account ineligible. Selected Skills and writer reject explicitly |
| Legacy regression | `regression.py`, `tests/regression/`: preserve legacy contradictions/exits/provenance; ten synthetic cases | Ten historical cases still lack original terminal association; no retrospective historical PASS |

Current Python package declares no third-party Python dependencies. Physical line inventory (including comments/blank lines, not reusable semantic LOC): 47 source files / 5,420 lines; 36 test/fixture files / 3,108 lines; seven scripts / 499 lines; one Skill / 36 lines. This is a baseline for reuse comparisons, not evidence that a replacement adapter would have the same size.

## Fresh Verification

Executed against the above unchanged source checkpoint, in Micromamba `ai-video-p2`:

| Verification | Current result | Meaning |
| --- | --- | --- |
| `python -m pytest -q` | **195 passed, 12 skipped**, 2.81s | Offline behavior; skips are explicit native/containment gates |
| `python -m pytest -q --native-conformance --containment-conformance` | **207 passed**, 32.26s | Pinned local Claude/Gemini runtime tests against fake upstream and containment probes; no live provider identity claim |
| Installed `subagent doctor --backend kimi` | `CONTAINMENT_QUALIFIED`; 20 OS checks true, native tool positive/negative probes verified | Current local containment; `live_identity=NOT_EVALUATED` |
| Current `read_qualification` + `verify_smoke` for worker/deep | Both `VALID_CURRENT_ROUTE_GATE` at 2026-09-19 11:44 UTC | Runtime bytes, immutable receipt artifacts, current private credential fingerprint and deep entitlement age verified without printing key |

For the full conformance run, `ROUTER_SANDBOX_IMAGE` and `ROUTER_SANDBOX_RUNTIME_SHA256` were populated from installed `sandbox.json`; `ROUTER_GEMINI_SANDBOX_CONFIG` and `ROUTER_GEMINI_RUNTIME_CONFIG` pointed to installed private configuration files. Neither was altered. No live generation is part of these 207 tests.

Installed source commit is the same HEAD; source/Skill package hash is `04b44ea87524bceb0f35d94cad6464832e417b4d4ba23e979fb57e6ef279d3ad`. Pinned Claude `2.1.277` binary SHA-256 is `722210f05ba494d8f6df69423c4d4f2960900f7a007d0532851c7a36e375cab7`; Docker image is `sha256:08efb085f717fe5792d7380a069c3f770422fa09770d904e6e2436e3706e0c85`.

## Live Evidence And Trust Limits

Private canonical receipts remain under `~/.local/state/agent-subagent-router/runs/`. The following existing receipts were read with `ReceiptStore.read`, which verifies their stored artifact hashes. They were not rewritten or re-executed for this table.

| Evidence | ID | Current readback |
| --- | --- | --- |
| Worker qualification | `27ba7e0c-32b1-41a9-8210-4f49474e0a30` | Valid current gate; canonical receipt SHA-256 `904ac7f68a6ddc1625a6e82e292f6d67da1143d73ef72d352fac3d01ba1fd357` |
| Deep qualification | `4f2d5dc8-4234-4665-b382-e82f1ad6cc00` | Valid current gate; receipt SHA-256 `5f3c17dcefcff35f54db521fa4c5435d8f9fb0b1da9ca4e108106a66cb767555`; entitlement observed `2026-09-19T07:44:28.697Z` |
| Recent deep project invocation | `8404fce9-9c2f-4875-b044-985c5724fa13` | `PARSED`, live, three wire requests, `parent_acceptance=NOT_EVALUATED` |
| Gemini account preflight | `c747cdfa-9b7b-42cf-a63b-915f4b39d633` | `GEMINI_INELIGIBLE`; zero generation requests; historical record identifies `UNSUPPORTED_CLIENT` |
| Kimi writer candidate | `c46437b7-9694-47d8-bf6c-2af958a2b4db` | Live `PARSED`, three wire requests; candidate output, not project acceptance |
| Parent candidate apply | `7568776d-f39b-43ed-861e-a748dee9d198` | `APPLIED`; subsequent project acceptance is a separate owner/record |

`worker`: provider Kimi, runtime Claude Code, client/wire `k3-256k`, requested effort high. `deep`: provider Kimi, runtime Claude Code, client `k3[1m]`, wire `k3`, requested effort max. Entitled/configured 1,048,576 context and actual 1M consumption are distinct; actual 1M consumption remains **NOT_EVALUATED**. Current observation proves authenticated endpoint declarations and transmitted effort fields, not remote internal computation. Qualification must be rechecked at final Spec review time; today's valid gate is not perpetual authorization or freshness.

M7's eight matched read-only tasks and M8's isolated test/apply/post-apply chain are documented in `docs/records/final-qualification.md`. They qualify their recorded environments and experiment scope, not every project/backend. This round has not repeated that entire live holdout experiment.

### Current Research Invocation

本轮另通过已校验的 installed `external-subagent` route 执行一次只读 Kimi deep 现状审计，**不是 final Spec review**。Task `current-truth-advisory`；sealed contract `648e2f0f91680739813babc0fc726f6ccebfba42cb46f7a11ce0c132beb1fe66`；receipt `f51ac150-9dc4-431d-b3a7-370e8a4cd332`。

该调用失败：`OUTCOME_UNKNOWN`，process exit 1，duration 363.2307s，两个 wire requests。首个请求为 authenticated endpoint `IDENTITY_VERIFIED`，request/response model `k3`、requested effort `max`；第二个没有 HTTP response/terminal identity。封存预算为 wall 1200s、idle 900s、request ceiling 16，输出未截断。没有自动 retry、没有修改 runtime、没有把不完整输出计作 review 完成。这说明当前 route 有可核实的身份边界，但一次生成的可靠完成仍可能失败；失败来源不能仅凭耗时归因于 provider 硬上限。后续正式双审若无法取得完整可信 Kimi result，必须停在 `REVIEW_BLOCKED`。

## Drift And Design Inputs

1. **Baseline status and runtime age.** Earlier Spec still says PROPOSED and refers to Claude `2.1.77` feasibility; status/records say its implementation was authorized and now use `2.1.277`. Preserve the frozen historical bytes and require a new explicit acceptance binding; do not silently relabel the old document.
2. **Stage/host descriptions.** The earlier inventory says router/Gemini/key unavailable, and some records/status say no remote/push. Current installation and Git state contradict reading those descriptions as current state. They are historical inputs, not permission to change runtime or push this round.
3. **OSS composition.** `docs/third-party-notices.md` explicitly says the router core did not directly reuse upstream implementation modules. Docker/official runtimes and stdlib primitives are reused, but this does not meet a claim of reusing mature CLI/router/projection modules. New research must revisit module-level reuse rather than repeat blanket REFERENCE_ONLY conclusions.
4. **Qualification meaning.** Route, containment, read-only experiment and writer evidence have different owners and validity conditions. `api.py` chooses provider-specific routes, and Gemini lacks the corresponding live qualification. A provider-neutral API shape is not proof of provider-neutral live conformance.
5. **Receipt dimensions.** Current process and observation facts remain available, but `project_run.py` overwrites one aggregate `classification` in precedence order. It does not expose all parse/evidence/identity/process dimensions independently as the earlier Spec describes. New design should make the transport/semantic separation explicit and testable without asking a model to generate these facts.
6. **Resolver coverage.** `_INSTRUCTION_NAMES` includes AGENTS/AGENTS.override/CLAUDE, not GEMINI. A GEMINI document is projected only if selected by another input path. References in constitution prose are not automatically resolved as a complete semantic dependency graph. A future native resolver must declare discovery, precedence, required refs and unsupported capabilities deterministically.
7. **Projection semantics.** Current Claude projection preserves bytes and duplicates applicable constitution content into a managed native rule. A source-map/byte check does not prove all nested instruction precedence or activation semantics. New design must avoid growing this into a universal giant prompt and should use reusable native projection surfaces where qualified.
8. **Timeout observations.** Supervisor idle is stdout/stderr activity, not semantic progress. The Kimi broker buffers the complete HTTP body before delivery (`KimiUpstream.__call__`), although the response may be SSE. Budget propagation is implemented and tested; an earlier approximately 300-second failed request does not by itself identify a provider-side hard limit. Unknown outcome is not safe automatic retry authorization.
9. **Writer atomicity.** `tests/unit/test_atomic_apply.py::test_edit_after_initial_preimage_check_is_preserved_and_conflict_recorded` explicitly proves a post-check race can leave candidate bytes at the target while returning `APPLY_CONFLICT`; the newer user bytes remain in the displaced inode. The exchange is not filesystem compare-and-swap. Long-term contract must describe recovery and parent disposition, not promise zero mutation on every conflict.
10. **Host and evidence trust.** Parent and host storage owner are trusted. Hashes bind bytes and detect accidental/in-scope tampering; they do not establish cryptographic nonrepudiation against that owner. Provider keys and broker capabilities remain outside model-visible contract/projection. Arbitrary repository documents are not proven secret-free just because their filenames pass a filter.
11. **MiniMax provenance.** `DONE_WITH_CONCERNS` with questions is a contradiction in its legacy protocol. The current five-field report avoids transferring lifecycle state to the model; it does not weaken legacy receipts. `"null"` ambiguity, tool mismatch, missing terminal/evidence and structured-output exhaustion stay distinguishable. Historical traceability remains unresolved even when synthetic replay passes.

These are research observations and requirements to settle during architecture exploration. They are not instructions to repair code in this round, nor a final dual-review blocker ledger.

## Ownership For The New Design

Repository constitution and project-native tests/Harness remain the business authority. Parent supplies the current task and accepted references, adjudicates findings, controls tests/apply/KEEP/REVERT/BLOCKED and remains accountable for completion. HarnessMesh may own deterministic resolution, delegated capability enforcement and evidence acceptance policy; mature reusable components should own the commodity mechanisms where their actual interfaces can satisfy these boundaries.

Research and implementation truth stay in their respective owners. The new Spec will own normative architecture after explicit approval, with unique clause ownership and source-linked evidence; neither this note nor reviewer consensus creates that approval.
