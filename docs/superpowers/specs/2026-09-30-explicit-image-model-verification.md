# Explicit Image Model Verification

## Authorization And Scope

用户在取消费用限制、获知6.1sol图片能力尚未证明后明确要求“验证”。Parent按任务内恢复规则授权Self-Review接受本窄修订：新增显式模型目录验证，不重跑旧quota恢复，不修改原seal、receipt或ledger。只适用unrestricted Codex subscription新probe及所选6.1sol/luna；不自动fallback。

## Contract

`observe-image-subscription --verify-model`仅在新probe绑定本文accepted SHA、原runtime/pins和实际native conformance成立后执行。Canonical subscription_account复用credential loader和固定HTTPS catalog getter；每owned probe只可提交一次catalog GET，先写OS UID host不可覆盖ledger。无quota GET、generation、refresh、retry。非法/失效凭据在GET前拒绝。重复probe、换state不能重放该观察。

新receipt `codex-subscription-model/v1`记录真实或synthetic evidence kind、model/credential fingerprint、probe ID、account_queries、provider_requests=0及匿名`model-evidence.json`。仅fixed catalog source/SHA、唯一exact slug及显式image input、authenticated facts和非未来24小时内观察可满足新policy的模型准入。事实补充matched_model_count、catalog_model_count和所选input_modalities的固定text/image投影，以区分未列出、重复、缺字段和明确text-only；不保存raw catalog、账号或凭据，不把缺字段解释成远端永久不支持。

原account receipt/默认observe命令和quota恢复计数语义不变，新模型证据不能成为预算、visual capability或semantic qualification。Selected model未证实时停止，零model请求。模型目录成立后只运行该probe的一次真实隔离八图capability；失败/unknown不得自动重试，原raw/native/identity/PNG/tools/secret/cancel/cleanup及truth-vs-review gates保持。

## Verification And Self Review

先red覆盖无quota、synthetic不可伪装认证、坏凭据零GET、state-independent no-replay、exact model/image、跨credential/错source/hash/未来拒绝；完整offline/native、Ruff/diff、Risk Gate及clean官方安装后执行一次显式真实目录验证。新入口不增加credential/TLS/工具权限或产品owner，复用原secret scanner和ReceiptStore；费用未知null。真实结果归原record，不篡改旧失败或宣称生产可用。
