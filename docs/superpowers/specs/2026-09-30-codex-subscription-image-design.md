# Codex Subscription Image Route Amendment

## Authority and Goal

当前用户明确“我没有openai的key啊你为什么不用codex”，此前已授权修复及安装受管视觉路线，并要求 MiniMax/GPT、禁止 Kimi。Parent 按当前任务内默认授权 Self-Review 接受本文；这不是用户逐字批准新 SHA 的声明。原 image、API、MiniMax Specs 与历史 receipts 不改写。本文为显式 Codex 订阅分支，不自动切换已有 API 调用。

## Verified Difference

Jianji 已用自己的 `<userData>/codex/auth.json` 登录，完成请求使用固定 `https://chatgpt.com/backend-api/codex` Responses 路线。本机应用登录文件存在且为 owner-only regular file；存在不证明当前有效登录、模型权限或额度。固定 Codex 0.154.0 不能证明预请求 hard generation cap，旧 API 分支因此要求独立 Key；该附加限制不能变成使用 Codex 订阅的前提。

[OpenAI authentication](https://learn.chatgpt.com/docs/auth) 区分 ChatGPT 订阅登录与 API Key 计费；文档不能替代本机认证/视觉证据。本文不升级 runtime，不读取 global Codex auth，不复制 OAuth 充当 API Key。

## Route and Credential Contract

新增显式 backend/profile `codex/subscription-bounded`，provider identity 为 `codex-subscription`。固定 HTTPS `chatgpt.com`，POST `/backend-api/codex/responses`，无 redirect、proxy、retry 或其他 provider fallback。复用原 strict image parser、seal、Docker native adapter、bounded Responses broker、ReceiptStore、qualification、installation owners；不能建立第二任务生命周期。

credential reference 仍为 provider/file，仅接受应用独立 `jianji/codex/auth.json` 的 private owned regular 文件，拒绝 symlink、global `.codex` 和 project 内路径。Canonical credential owner 读取并投影 access token/account ID；其他读取到的 auth secret 仅用于泄漏检测，不进入 runtime、prompt、argv、mount、raw receipt、日志或错误。Broker host-memory 发实际 OAuth Bearer 和 account header；Docker 仅持 invocation-local opaque capability。无 login、refresh、购买、充值、全局认证变更或 token 持久化。

## Explicit Finite Budget Change

仅本新 profile 的 `budgets.generation_tokens=null`，明确表示 **预请求生成 token 上限不支持**；新增 `observed_output_tokens_limit=2048` 是事后拒绝超限的条件，不能称为 upstream hard cap。API、MiniMax、旧 project budgets/schema 仍保留原 hard cap，不能接受 null。Native 请求不得含 `max_output_tokens`，映射只校验和投递原 bytes，receipt 明确记录未施加 hard token cap。

本次 capability 最多一个订阅 model request，wall 180 秒、idle 90 秒、8 张 128×128 PNG、PNG 1MiB、payload 65536 bytes、response/output 1MiB、context 1MiB。一次不可恢复的 host ledger reservation，在发送前消费；改变 task/state/context 不能恢复。wall/output 限制不能证明 upstream 已停止计量；unknown outcome 保留未知并停止。订阅额度按服务计量，tokens/cost 未知记录 null，不计为零；不触发额外 API 账单、升级或超额付费。已有 API once/USD1 授权不转移、不恢复，MiniMax live gate 仍为零，formal authorization 仍为零。

发出这一次 capability 前必须有 owner 签发并绑定 credential fingerprint、actual input digest、profile/model/effort、当前认证订阅额度及 observation timestamp 的 immutable account/budget receipt。未认证、额度未明确可用、模型/视觉权限未知、required engineering review 未完成均为 INCOMPLETE，零 model 请求。Quota 查询只允许固定 ChatGPT account endpoint、最多一次、无 retry/refresh；它不是生成请求或视觉 proof。

## Response and Qualification Gates

复用原 full PNG 顺序/hash、tools=[]、fresh ephemeral context、native thread/turn/item 和 upstream identity、SSE 完整关联、secret scan、terminal、strict JSON、revoke/drain/cleanup/quarantine。订阅 completed response 可以缺省/null `max_output_tokens`；任何非 null cap 宣称均拒绝。完整 integer usage 的 output_tokens 必须不超过 observed limit。原始 native、实际上游、完整响应及各自 proof 单独绑定，不以模型自述或 fake transport 当视觉证明。

独立 router-owned random eight-image capability 只能得到 ROUTE_CAPABILITY_ONLY，不能成为 M5-D2A 真值 qualification。新 tuple 和 envelope 明确 null hard cap/observed limit；旧资格/安装/文本成功不继承。A/B/joint 的全部 semantic gates、holdout、冻结、coverage 与真实媒体分层不变。PRODUCT_DISABLED、source authority=none/eligible=false、全部生产阶段 BLOCKED。

## Plan and Verification

按 writing-plans 更新现有 implementation plan；current working tree，无 worktree/push。先否定测试与 offline/native Docker/containment 验证，再进行一个 exact-snapshot read-only native reviewer_max full review；本订阅分支最多两轮，各900秒，历史 Kimi2/native1–18不删除、不重置。Parent 调查 findings、裁决；无 unresolved blocker 才 specific-path commit、官方 clean installation、installed pins/Skill/CLI/native/OS 校验。缺条件诚实 INCOMPLETE，不要求用户再提供 OpenAI Key。

## Self-Review

唯一新增的认证边界归 canonical credential/broker owners；唯一生成预算变化限定显式订阅 profile，清楚区分 unsupported hard cap、postflight rejection 与有限 request/time/bytes。该取舍容许一次使用已有订阅的能力探针，但不声称严格 token 费用封顶。缺账户/模型/用量证据时门仍关闭；没有绕过图片隔离、receipt、独立真值、资格或产品禁止。
