# GPT Astra Image Route

## Goal and Authorization

简辑用户明确允许核验并选择应用独立账号实际支持图片的 GPT 型号。2026-10-01 原应用空闲时经 `connection.chatgpt.refresh` / `ChatGPTSession.readAccount` 读取的新目录列出 `gpt-6-astra`，该 owner 已过滤 hidden/text-only 型号；证据在私有 `auto-contour-full-20261001-51kctk6d/application-model-catalog.json`。Parent 选择并冻结 `codex / subscription-bounded / gpt-6-astra / high`；不修改应用现有选择，不声明目录即视觉资格。

## Contract

只有新 seal 同时绑定本文件 exact SHA、原 subscription、unrestricted spending、model verification refs，才允许该精确 tuple。原 `gpt-6.1-sol` / `gpt-6-luna` 和旧任务保持其合同，不允许任意 GPT、别名、自动 fallback、重试或 auth refresh。新型号仍须原固定 HTTPS catalog 精确匹配唯一且显式支持 image 的 canonical account evidence；应用 RPC 目录不替代该 gate。

复用原 `image_contract.py` 的 tuple gate、`subscription_account.py` 的一次目录观察、原 `cli.py`、`codex_image_wire.py` 请求校验；不新增 provider、凭据 owner、endpoint、网络 wrapper、资格 issuer 或预算恢复。原 source seal、installed binding、Docker、opaque credential、PNG 字节、tools=[]、单次提交、wall/idle/bytes 和收敛 guards 不变。

### Responses Lite Revision

原 classic wire 假设被真实 fake-only native conformance `4c112824-79fc-4ee6-afcb-7ebd798f65a5` 推翻：provider_requests=0，projection 拒绝。固定 runtime 的 `core/src/client.rs` 用 model metadata `use_responses_lite` 将空工具与 sealed base instructions 移入 developer input；world_state 另注入两段内置 multi-agent 控制消息。不能将缺失 top-level instructions/tools 当成任意字段放行，也不通过改 model metadata 伪装 classic protocol。

此修订仅允许 exact Astra tuple 的一种精确 Lite native 投影：top-level fields 恰为 model/input/tool_choice/parallel_tool_calls/reasoning/store/stream/include/prompt_cache_key/text/client_metadata；parallel_tool_calls 必为 false（runtime 对 Lite 显式禁用并行工具），tool_choice=auto、store=false、stream=true、include=[reasoning.encrypted_content]；reasoning 恰为 effort=high、context=all_turns；text 恰为 verbosity=low。input 恰按顺序为 tools=[] 的 additional_tools developer item、仅含 sealed system_text 的 developer message、两个下述精确控制 message、原 sealed user text 和全部原 PNG。各 item ID 按 at_/msg_ UUIDv7 核验并不得重复；原 metadata、原图片逐字节/尺寸/顺序、单 user、预算和无工具门保持。Classic Astra 请求不再接受，历史型号不变。

额外两个 developer message 仅允许固定顺序的 SHA256 `47091490938505958b0c22ff42db6fd79b272a2af6923166f4c2cc53c4fe0df4` 与 `6ded806e3cdbb35599ecaf8742574bc5274908472b1729090010c404c2151e8e`，每项只能有一个 input_text，任何字节、role、shape、顺序变化或额外上下文均拒绝。它们是该 pinned runtime 的基础设施注入，不是 sealed task。原 mapper 在已严格验证后机械移除这两项，actual provider wire 仍使用 Lite input 的空 additional_tools、sealed system 和 sealed user，不发送这两段 Agent 指令。proof 同时记录原 native、actual request 摘要、投影版本和移除的两个摘要，保留差异而非声称 wire 完全未改；不识别或执行其中的工具建议，不开放 context normalization。原 source/runtime/install/Docker seals 必须重新冻结，旧失败不重放。

本地 native conformance 必须核验实际 runtime 发出的结构及 PNG；实际 HTTP 目录缺能力时零 generation。探针仍是原八张随机位置图片含重复像素，判据保持精确一致，失败保留，不重放。

## Acceptance and Self-Review

无本修订 ref、错误 tuple/effort/backend、目录缺失/重复/text-only、fake account 均拒绝；旧路线测试不变。实际新 native conformance、一次目录和至多一次该 owned probe 的真实能力请求分别记录。QUALIFIED 仅适用 owned 八图 capability envelope，source semantics 与 formal execution 仍 NOT_EVALUATED，产品保持关闭。任务内必要合同修订由 Parent 按当前 global 授权 Self-Review 接受，不伪造用户另行批准 exact SHA。
