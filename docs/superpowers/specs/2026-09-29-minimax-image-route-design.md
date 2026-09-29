# MiniMax Sealed Image Route Amendment

## Authorization and Goal

2026-09-29 用户在同一 M5-D2A 任务明确选择 MiniMax + GPT，禁止后续 Kimi，并提供 Jianji 已保存 MiniMax-M3/Responses 连接的截图。按当前 global Execution Mode 的任务内合同默认授权，Parent Self-Review 本窄修订后进入工程实施；不伪称用户逐字批准新 SHA。旧 accepted Specs、Kimi/GPT receipts、失败及消费原样保留，acceptance owner记录新的具体来源。

目标是在原 image-only owners 内新增显式 MiniMax 路线，复用 sealed inputs、Docker、broker、ReceiptStore、预算、conformance 与 qualification；不能将 Kimi 或 Codex 的身份改名。GPT 原 api-bounded 路线保留，项目 worker/provider选择合同不变。

## Route and Input Contract

新增 image backend=minimax、profile=responses-bounded、model=MiniMax-M3、effort=provider-default。这是用户应用实际保存的模型；不升级到 M3.1、不替用户改配置。TLS 仅 `api.minimaxi.com`，POST `/v1/responses`，不追随 redirect、不切换到 `.io` 或 `.cn`；国内文档当前重定向至 `.cn` 的事实保留，当前账号/原host可用性未证明时 live仍INCOMPLETE。

原完整 PNG 逐张传入，匿名 image IDs/顺序/system/task 与 seal 绑定；每图≤10MiB、总payload≤32MiB，PNG本地校验独占。单条fresh user input，没有历史、truth、场景标签、对应关系或对方结果。`tools=[]`、`tool_choice=none`、`stream=false`、`store=false`、`max_output_tokens=sealed generation_tokens≤2048`；不依赖 ignored runtime配置、事后usage或可见文本截断替代hard cap。

MiniMax 使用固定的 Python Responses runner，在新的immutable Docker image内仅发一次 loopback request并输出完整typed终态；不是 Claude Code/Codex app-server，也不声称 Anthropic/OpenAI 模型身份。复用原 Docker entry、network=none、source=None、readonly、UID/caps/AppArmor/seccomp、无host auth/mount、revoke/drain/cleanup。模型不具备文件/搜索/命令/委派工具；Python的宿主执行能力不是模型工具。

## Transport, Credentials and Receipts

在现有 bounded Responses broker中建立明确的固定 MiniMax 分支，复用其Unix capability、TLS单次发送、secret scanner、quarantine及publication状态机；不新增第二broker lifecycle或credential store。Codex原映射/metadata/identity checks保持，未知backend零wire拒绝。

复用原provider-private reference/loader保护。Jianji已保存API credential存在；author preparation先从canonical ConnectionStore只读发现，后续安全handoff须由原owner产生，不能让router Python重写Jianji配置schema或读取global Codex auth。本文不授权Key输出到聊天、argv、prompt、runtime env/mount或正常receipt。缺安全handoff/真实账号事实时零live请求；不得以helper CONFIG_FOUND签发预算。

验证完整JSON Responses：authenticated request ID/response ID/model、completed、usage输入/输出整数且生成≤cap、store=false、只有message/reasoning、message内容仅output_text；error/incomplete/工具/非法输出拒绝，原body只在现有secret/type检查通过后保存。MiniMax没有被公开示例证明的cap echo，receipt标明hard cap来自实际已校验request，不伪造上游回显字段。输出便利字段如存在必须与message文本一致，完整strict JSON_OBJECT/v1才交付。保留原请求、原响应、mapped/canonical输出的exact hashes和route tuple；失败仅隔离摘要，迟到不得升级。

## Budget and Qualification

工程 fake/native/OS不调用商业服务。新MiniMax capability最多一次，预算receipt尚未存在且费用授权保持0；在实际账号、input/image保守accounting、当前价格与余额证明冻结前不产生请求。不能转移旧Kimi预算、复用GPT payload成本或在新state目录重置host消费。正式holdout仍零费用授权/零请求；任何新增费用需按当前任务规则形成可信canonical预算后才可进入live。

新MiniMax tuple单独有router-owned 8-image probe、native/OS conformance、真实视觉qualification。旧refs及GPT/Kimi conformance只证明其旧tuple；MiniMax fake通过不等于视觉能力。Qualification仅ROUTE_CAPABILITY_ONLY、source semantics NOT_EVALUATED、authority=none、eligible=false。Jianji正式A/B资格仍须全部独立truth、criteria/config/inputPlan/budgets及raw/mapping/joint/correspondence/可信issuer门，PRODUCT_DISABLED及全部production BLOCKED保持。

## Verification and Review

先严格red-green验证完整PNG保真、身份/未知分支、exact request/cap、工具/上下文/额外字段、错误/不完整/usage/secret/终态/receipt关联、缺账户零wire与一次消费。Fresh全套offline、显式native/fake+OS、Ruff与diffcheck；稳定candidate按base Risk Gate判断。新credential/TLS分支触发critical review，用户已禁止Kimi，沿本任务原native fallback，最多两轮read-only reviewer_max、每轮900秒；历史Kimi2/native1–15不重置，新finding须调查后才有限修复/复核，不能自动循环。

通过required review及Parent裁决后仅specific-path clean commit，再用官方installer安装并核对entry/Skill/package/new Docker pins及installed native/OS；不编辑installed tree。缺有效review、containment或原host证明不得宣称engineer route complete；缺live条件真实记录INCOMPLETE，不能模拟资格。

## Sources and Self-Review

Primary [MiniMax image input](https://platform.minimax.cn/docs/api-reference/text-openai-api) 与 [Responses fields/status/usage](https://platform.minimax.cn/docs/api-reference/responses-create) 支持M3原生图片及生成上限；国内文档host变化已单列，不能静默切换应用连接。文档只是candidate接口证据，未证明本账号能力。明确独立backend/runtime、request hard cap与response proof区别、credential handoff/有限预算缺口、旧tuple兼容、required review/installation和无产品授权；没有重复identity/knowledge/admission owner或provider fallback。
