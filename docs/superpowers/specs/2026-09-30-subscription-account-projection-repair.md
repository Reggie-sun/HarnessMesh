# Subscription Account Response Projection Repair

## Authority and Evidence

当前任务已授权修复受管路线及任务内有限预算/恢复规则。Parent Self-Review接受本窄修订；不是用户逐字批准新SHA的声明。原订阅Spec、first once ledger及失败receipt不改写。

Installed b120f40的真实quota GET以UPSTREAM_SECRET_REFLECTION结束，account receipt f287b749-4246-4cf0-9b40-61b8fe8bd7b5、account_queries=1、provider_requests=0；catalog未请求，未发送模型请求。原raw因保护门未保存，不能断言具体反射项。OpenAI pinned0.154.0 [official types](https://raw.githubusercontent.com/openai/codex/rust-v0.154.0/codex-rs/backend-client/src/types.rs)明确quota response可以包含account_id；独立合成重现证明原扫描会拒绝正常匹配账号字段。

## Projection Contract

仅固定quota endpoint、HTTP200、strict JSON顶层account_id为字符串且精确等于当前credential.account_id时，在host内验证后移除该字段再扫描其他内容。字段存在但类型/值不符拒绝；字段缺省沿用JWT关联和HTTPS认证。Token/refresh/id-token及账号在任何其他位置反射仍拒绝，catalog不豁免。返回parsed对象不含此账号字段，仅raw SHA可进入既有匿名facts；不保存raw或输出账号。不是关闭secret guard，image broker仍原样全量拒绝。

## Finite Explicit Recovery

新增显式CLI --recover-account-projection；默认原once拒绝保持。仅在旧不可恢复host ledger存在，并且同一canonical store中的其previous invocation receipt为codex-subscription-account/v1、UPSTREAM_SECRET_REFLECTION、account_queries严格integer1、provider_requests严格integer0、model/fingerprint与当前一致时，允许新独立不可恢复recovery ledger一次额外quota GET及原尚未执行的catalog GET。必须sealed refs绑定本文SHA及fresh native conformance；旧receipt/ledger不删除、不返还、不覆盖，换state不能取得恢复。预算总计quota最多2、catalog最多1，generation请求仍最多1、formal0。Unknown、timeout、credential拒绝等不进入该恢复，任何后续失败停止，不再自动追加。

## Verification and Review

真实旧扫描合成red、matching/mismatched/其他位置/token/catalog否定测试；receipt/host ledger/state/类型与consumption测试。Fresh完整offline/native/OS/Ruff/diff后一个同一read-only reviewer_max round24、wall600秒，保留Kimi2/native1–23及account已耗次数；Parent裁决无unresolved blocker后scoped clean commit、官方安装及新tuple installed conformance，再显式执行此一次恢复。没有自动round25或再次live恢复，unsupported cap=null/observed2048及全部产品禁止不变。

## Self-Review

Canonical credential/account/budget/CLI/receipt owners不变；限定已知HTTP响应被本地guard拒绝的只读恢复，不重试未知模型生成。原base query已耗用、真实反射原因未确认的事实保留；新一次结果须真实验证，不以本修订或测试代替资格。
