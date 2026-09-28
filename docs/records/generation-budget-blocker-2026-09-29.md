# Codex Image Generation Budget Investigation

## Status and Authority

2026-09-29 用户要求“先修复blocker然后安装新路线”。既有 image supplement SHA `c1169a61ba8573a2c4ce442b321683a65b800230d3e8620e069e388a6d97c0f1` 已批准并实施 input-only checkpoint `ea05c07`；此次继续调查其 actual generation gate，不回到 DESIGN_ONLY，也不把该 checkpoint 写成完整视觉路线。

当前 `INCOMPLETE / INSTALLATION_NOT_REPLACED / VISUAL_NOT_EVALUATED`。原订阅路线的硬生成上限仍未得到证明；新 API 修订处于 exact-SHA approval pending。现有 source/package、成功文本请求和 native/fake 不能替代真实视觉能力或 Jianji truth-vs-review qualification。

## Verified Root Cause

Pinned Codex 0.154.0 binary SHA `3188814c35471432d4123203e0eb38e5bddc60226e3d7ddf0e59e649ea140022`，Docker diagnostic image `sha256:4348c225136362d3e85d82c0251db00991950e07fd07e244acaecbd6a00fd1d9`、helper SHA `93283e67d2c40e596389db9ee59c8b261da6082f7df99eeed925ba714852a959` 保持。当前实际捕获请求无 `max_output_tokens` 等 generation setter。`model_max_output_tokens=2048` 仅见于 origin 元数据，effective config 没有数值；RPC `TurnStartParams` 的 outputSchema 约束最终 JSON，不能限制生成 tokens。usage/compact/tool-output 限制同样不能代替该门。

对应 [官方版本 request source](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/codex-api/src/common.rs) 的 `ResponsesApiRequest` 无 generation cap 字段；本地保存14294 bytes、SHA `27a9f516c8ec8d38dbf0ba03d6325e24e81c1e751f3195492040adfc8a4cd3cc`。第二份 [versioned config](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/core/src/config/mod.rs) 下载遇到 TLS `SSLEOFError`，没有重试或伪造缓存 SHA；该文件另经 web tool 只读核对。Native read-only mapper 独立核对本地 schema/capture，Parent 复查实际源码和请求，不把 mapper 推断当服务端证明。

本轮显式 native/fake+containment 单项测试实际运行，`1 passed in 1.90s`。这项测试证明原八张 PNG 顺序/identity、tools=[]，以及 `require_native_generation_bound(body, 2048)` 真实以 `IMAGE_GENERATION_BOUND_UNPROVEN` 拒绝；不证明 blocker 已修复、turn 完成或视觉语义通过。没有新商业视觉请求。

## Proposed Repair and Approval Boundary

[API amendment](../superpowers/specs/2026-09-29-codex-image-api-budget-design.md) 已 Self-Review，SHA `14e10cad0f3afc44f0f3796c2ae86c45e161c8a17ab2d54801c8c261a81df272`，`EXACT_SHA_APPROVAL_PENDING`。推荐新增明确 `api-bounded` profile、固定 OpenAI Responses API/应用独立 API Key，broker 只增加冻结的 `max_output_tokens`，分别留存 native 原请求与实际上游 body；保留 Docker/seal/no-tools/全部资格门。官方 API [reasoning guide](https://developers.openai.com/api/docs/guides/reasoning) 支持包含推理 tokens 的该硬上限，但文档不是本机 live 证明。

这是 endpoint、credential、billing 的实质改变。Base V3 要求用户对新 exact SHA 批准，此前 router 范围授权不能推定新计费路线已批准。用户已收到互斥选项：批准 API 修订及最多一次新增 OpenAI probe、USD1 cap；保留订阅路线及 blocker；或明确先实现/安装 Kimi-only，Codex/formal 继续阻断。以选项完整语义为准。尚未收到新批准；不实施、安装或静默 fallback。正式 holdout cost authorization=0 不变。

## Managed Delegation and Failure Evidence

按 external-subagent Skill执行受管 Kimi deep/max 安装边界 mapping；限定只读 `image_inspect.py` 与 `installation.py`，没有 holdout/truth、修改、工具扩大或 final-review 权限。Seal `a0c27a7ce0da864d89550a3cbd82426594a7745e13a4c021d891de86460c02c5`，qualification `4f2d5dc8-4234-4665-b382-e82f1ad6cc00`，invocation `458263c6-9b67-493e-86cf-e77be7e57ef6`。有限 wall240/idle120、requests3、generation8192、output8MiB/context512KiB；这属于独立工程 mapping，非视觉或 formal 预算。

Canonical receipt 为 `OUTCOME_UNKNOWN`：13.803441s、exit1、无截断、wire attempts2。第一个 authenticated `api.kimi.ai / k3 / max` HTTP200，output107；第二个 CONNECT `TLS_ERROR`，无 HTTP/身份响应。Parent 核对两次实际 Read/source SHA、三个 canonical artifact SHA/size、qualification binding；未采用报告、无 orchestration retry/fallback。actual cost=null。Receipt 的 `descendants_terminated=false` 保留，不倒填完成；只读 Docker 核对未见该 invocation 存活容器，不停止其他现有容器。此 mapping 失败不是 final reviewer verdict，也不占 final review 三轮预算。

## Installation and Shared Ownership

Parent 实际核验官方 installation owner、managed wrapper/Skill 及 installed CLI hash checks：安装仍 pin source commit `bba056309342f3f55a62e7cb9378a4c6d96503ec`、clean-at-install，source hash `6aea7fb98886712bb0f42e3449c41acc51c83acd3f0d0f478d8fb6a84fc4d879`；entry SHA `7d298cf0b8c31b591cdb5e18003c2f3dc665f7819e96e18328acc6060f79ecdf`，Skill SHA `a82abac901b7c60b3a49b0d192d8950d49cd99984beb407fe7bde5e116af5ede`。未调用 install、未修改 installed tree/wrapper。安装函数本身不签 route/semantic qualification，Parent 必须先满足工程门。

调查后发现另一个任务拥有 api.py/cli.py/contracts.py 及相关 budget/conformance tests 的未提交改动，全部保留，本轮仅自身 docs；不能覆盖、stage 或将混合 source 安装成自身 verified candidate。此前 full offline397/native420 的记录保持历史 snapshot，不冒充当前混合源码 fresh 全套验证。

## Evidence and Remaining Work

独占 `/home/reggie/.local/state/agent-subagent-router/generation-blocker-investigation-20260929` 保存13项 diagnostic/test/schema/installation/managed receipt 与观察材料，manifest SHA `ae3ae436755c0b0f60d2a3765a524884a360ce1bdb84be5d4f51a11af6caaf80`；该 manifest 仅工程归档，不建立第二 ReceiptStore 或 qualification owner。源代码未改变，无适用新增 implementation review；API credential/TLS 实施后须 native verification、base G2 required managed review及Parent裁决。

批准修订后自动更新 existing implementation plan，继续真实 authenticated channel、native completion、image execution/typed receipt/qualification owner及预算验证，通过 required review再 official clean-source installation及 installed verification。只有全部 capability 条件成立才有限 probe；正式 blinded qualification 还须 Jianji 全部门和独立预算。当前真停止门为新 endpoint/billing exact-SHA approval；产品始终 disabled、authority=none、eligible=false，所有生产阶段 BLOCKED。

本轮仅 own docs，已读取verification-before-completion并检查 diff；不修改/stage/commit其他source，也不声称当前混合tree full suite已通过。新的draft SHA保持展示字节，required implementation reviewer只在批准后实际新credential/transport实施达到native verified stable candidate时调用。稳定文档checkpoint记录诊断和待批准修复，不构成新route installation或completion。
