# GPT Astra Image Route

## Goal and Authorization

简辑用户明确允许核验并选择应用独立账号实际支持图片的 GPT 型号。2026-10-01 原应用空闲时经 `connection.chatgpt.refresh` / `ChatGPTSession.readAccount` 读取的新目录列出 `gpt-6-astra`，该 owner 已过滤 hidden/text-only 型号；证据在私有 `auto-contour-full-20261001-51kctk6d/application-model-catalog.json`。Parent 选择并冻结 `codex / subscription-bounded / gpt-6-astra / high`；不修改应用现有选择，不声明目录即视觉资格。

## Contract

只有新 seal 同时绑定本文件 exact SHA、原 subscription、unrestricted spending、model verification refs，才允许该精确 tuple。原 `gpt-6.1-sol` / `gpt-6-luna` 和旧任务保持其合同，不允许任意 GPT、别名、自动 fallback、重试或 auth refresh。新型号仍须原固定 HTTPS catalog 精确匹配唯一且显式支持 image 的 canonical account evidence；应用 RPC 目录不替代该 gate。

复用原 `image_contract.py` 的 tuple gate、`subscription_account.py` 的一次目录观察、原 `cli.py`、`codex_image_wire.py` 请求校验；不新增 provider、凭据 owner、endpoint、网络 wrapper、资格 issuer 或预算恢复。原 source seal、installed binding、Docker、opaque credential、PNG 字节、tools=[]、单次提交、wall/idle/bytes 和收敛 guards 不变。

`gpt-6-astra` 的 wire 仍按原 Codex 订阅协议校验精确 model/high、无 text verbosity 与 reasoning.summary=auto；本地 native conformance 必须核验实际 runtime 发出的结构，不能通过放宽字段来掩盖不匹配。实际 HTTP 目录缺能力时零 generation；探针仍是原八张随机位置图片含重复像素，判据保持精确一致，失败保留，不重放。

## Acceptance and Self-Review

无本修订 ref、错误 tuple/effort/backend、目录缺失/重复/text-only、fake account 均拒绝；旧路线测试不变。实际新 native conformance、一次目录和至多一次该 owned probe 的真实能力请求分别记录。QUALIFIED 仅适用 owned 八图 capability envelope，source semantics 与 formal execution 仍 NOT_EVALUATED，产品保持关闭。任务内必要合同修订由 Parent 按当前 global 授权 Self-Review 接受，不伪造用户另行批准 exact SHA。
