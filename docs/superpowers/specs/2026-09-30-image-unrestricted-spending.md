# Image Unrestricted Spending Amendment

## Goal And Authorization

用户于2026-09-30明确要求“预算不用管,也不应该设限制”。本修订只作用于当前M5-D2A所选MiniMax与应用独立Codex subscription image路线；用户承担该任务调用费用，不再要求余额、价格、input-token估算或financial budget receipt，不设任务金额、token或累计调用次数上限。此授权不启用产品，不替代视觉/语义资格。

## Sealed Policy

新 `image-task/v1` 使用匿名metadata `spending_policy=unrestricted`，且selected_refs绑定本修订的exact accepted SHA。适用tuple仅 `minimax/responses-bounded/MiniMax-M3/provider-default` 和 `codex/subscription-bounded/gpt-6.1-sol|gpt-6-luna/high`。Unknown policy、其他backend/profile/model、缺accepted修订拒绝；旧seal、budget/account receipts、reservation ledgers和历史结果原样保留，不改变其执行含义。

新policy中generation_tokens=null；Codex observed_output_tokens_limit=null，MiniMax不发送max_output_tokens。Typed非负usage照实保存，不因output token数超过旧2048而拒绝；未完成/截断响应仍拒绝。费用未知为null，null意味着未施加金额/token上限，不能填写0或伪造余额。

## Independent Gates

MiniMax原hardcoded IMAGE_MINIMAX_BUDGET_NOT_AUTHORIZED不作用于新policy。Codex不再要求quota_available、余额、成本或旧probe-budget receipt，但仍核对canonical authenticated model-image evidence与current credential fingerprint/model；只有认证目录明确支持所选image输入才准入，失败为SUBSCRIPTION_MODEL_UNVERIFIED，不称为预算不足。Model observation的身份、真实HTTPS provenance及非未来时间仍必须核对。新policy并不把既有image_input_supported=false改为true，不自动追加catalog请求。

Live仍须valid application credential、当前sealed runtime/pins、router-owned eight-image probe、实际Docker/native conformance、完整PNG/顺序与raw/native响应关联。Formal owner/隔离config/输入包络尚未成立时拒绝为IMAGE_FORMAL_EXECUTION_UNAVAILABLE；不再把未实现的formal入口描述为缺费用授权。

## Request Lifecycle

每个sealed invocation一次wire submission，仍保持broker request_limit=1；这是一次性提交与no-replay协议，不是任务累计调用额度。新policy的host reservation改为每个owned probe一次，不以backend全局once耗尽任务授权。相同probe/unknown调用不得重放；新probe不会改变旧receipt或提升旧失败资格，也不能因换model或追加诊断直到通过而掩盖已证实硬错误。

单次wall/idle deadline、bounded input/output bytes、image尺寸、context内存、Docker隔离、工具禁止、秘密扫描、取消/revoke/drain和迟到隔离继续执行，均不声称为financial budget。不得自动retry/refresh/fallback。Finite dataset inputPlan决定正式工作量，false EMPTY及其他hard semantic gates仍零容忍；独立truth和A/B/joint要求不变。

## Ownership And Verification

复用image_contract/process/budget/probe/run/wire/broker与ReceiptStore；不建立第二credential/authorization/source/product owner。CLI prepare-image-probe增加显式--unrestricted-spending，旧默认与旧CLI receipts兼容。新receipt明确记录spending_policy，不将其称为视觉或生产qualified。

否定/兼容测试先确认旧门真实失败，再覆盖accepted-ref/tuple/policy、null token cap、typed usage大于2048、no max_output_tokens、缺image权限/错fingerprint/合成account、旧caps/旧once不变、new per-probe no-replay、formal owner缺失及tools/secret/取消回归。Fresh offline/native+containment/Ruff/diff、critical工程review、Parent裁决、clean官方安装和installed OS/native proof成立后才考虑实际capability；没有image权限仍保持真实0请求/INCOMPLETE。

## Self Review

本修订尊重最新用户的费用授权，移除额度/成本前置门而保留身份与资格owner；没有通过账务字段伪造能力、篡改历史、重复未知付费请求或启用产品。正式shape审阅的预算条款只在金额/token/任务调用总量上被本修订替代，runtime生命周期与受控输入冻结继续适用。
