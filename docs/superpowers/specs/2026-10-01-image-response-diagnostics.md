# Image Response Rejection Diagnostics

## Authorization And Scope

当前用户要求继续“完整验收”，此前已授权 router 扩展与安装、指定 MiniMax + gpt-6.1-sol、禁止 Kimi。按任务内合同变更默认授权，Parent完成本窄合同 Self-Review 后实施，不新增用户批准步骤。旧接收合同、once ledgers、失败 receipts 与结果原样保留。

真实 MiniMax receipt `c5ab6f78-77a0-4441-83a6-fcf609369cfb` 收到 HTTP 200，却只有 `IDENTITY_UNVERIFIED` 和隔离摘要；不知道是 request ID、model、completion、storage 或其他身份条件失败。现有检查继续 fail closed；本修订只允许记录固定拒绝标签，不能猜原因、放宽校验或发布被隔离文本。

## Diagnostic Contract

唯一 validator仍为 `minimax_image_wire.validate_minimax_image_response`；原 `RouterError.code` 和 rejection/qualification结果保持。其 `detail` 仅使用源码固定枚举，定位重复header、request ID缺失/冲突/非法、response ID非法、request ID错配、object/status/model/storage/error/incomplete及item ID问题；不包含值、header名称列表、provider文字、Key、账户、请求/回复正文。

原 broker完成完整响应 secret 检查后才调用validator。仅 MiniMax且detail严格匹配静态allowlist时，隔离摘要与observation增加 `response_issue`；任意错误detail、其他backend、secret拒绝不投影。仍只保留失败body摘要，模型/runtime收不到正文，无执行/重试/恢复/资格权限。

## Verification And Live Boundary

先用offline负例证明当前无法定位各identity拒绝，再验证固定标签、未知detail不泄露、split/escaped/header秘密先拒绝、cap/identity/storage/工具/late-output原门不变；运行full offline/native Docker/fake、Ruff及diff，按base Risk Gate判断后scoped clean commit和官方安装。安装后用新probe验证新pins/Docker，显式一次诊断请求获取具体失败标签；不重放旧probe，不改历史分类。若已知外部身份/账号或路线条件不满足则停止真实请求；不以新probe机械重试至通过。

## Self-Review

新增输出为有限静态标签，不提供新authority，不输出原始秘密或模型文本，不改变准入与publication。可信validation、credential、TLS、隔离、no fallback、全片真值与产品gates保持原owner。正式项目执行和qualification仍取决于原独立条件；本diagnostic不能代替它们。官方接口仅为候选协议参照：[Responses reference](https://platform.minimax.cn/docs/api-reference/responses-create)；当前固定账号host仍为api.minimaxi.com，不静默迁移。
