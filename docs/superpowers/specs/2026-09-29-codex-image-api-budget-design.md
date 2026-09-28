# Budgeted Codex Image API Route Amendment

## Status and Authority

DRAFT / SELF_REVIEWED / EXACT_SHA_APPROVAL_PENDING。用户要求“先修复blocker然后安装新路线”；本文件准备可审阅修复，尚未授权实施新的API端点或计费路线。当前 [base architecture](2026-09-23-harnessmesh-rare-review-design.md) SHA a3c216c077608767e1ac7ac7d03869e8d90f49256469691e8206c71edbf3566c 与 [image supplement](2026-09-29-image-only-route-design.md) SHA c1169a61ba8573a2c4ce442b321683a65b800230d3e8620e069e388a6d97c0f1 保持原字节及约束。本文是后者Codex authenticated transport边界的窄修订；批准仅由既有 acceptance owner绑定本文exact SHA。base V3要求语义必须改变时取得新exact SHA批准，不能把“修复”解释为已经批准新付费服务。

## Verified Blocker

Codex 0.154.0实际Docker/fake请求无max_output_tokens；model_max_output_tokens=2048只出现在配置origin元数据，effective config和wire均无数值。对应官方版本源码的ResponsesApiRequest没有generation cap字段，config无model_max_output_tokens。官方maintainer也记录移除该参数支持。现有hard generation≤2048与固定chatgpt.com/backend-api/codex路线，当前没有满足两者的可验证实现；不声称所有未来订阅端点永远不支持。

参考：[pinned request source](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/codex-api/src/common.rs)、[pinned config source](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/core/src/config/mod.rs)、[maintainer decision](https://github.com/openai/codex/issues/4138)。本地原请求、版本/binary/image hashes和历史失败由工程record独占；公开文档不能替代当前live identity/probe。

## Approaches and Selected Proposal

A，推荐：为Codex image backend新增明确profile api-bounded，通过固定OpenAI Responses API端点施加真实max_output_tokens，并继续使用现有pinned native Codex app-server和Docker输入。使用独立OpenAI API Key及API计费；不把ChatGPT订阅/OAuth凭据当API Key。官方 [reasoning guide](https://developers.openai.com/api/docs/guides/reasoning) 与 [token counting guide](https://developers.openai.com/api/docs/guides/token-counting)明确API该上限包含可见、推理和其他非可见生成tokens；实际受支持行为仍须新fake/live证据。

B：用户明确缩小到先完成并安装Kimi image route，保留Codex blocker和M5-D2A INCOMPLETE；这不签双模型资格，也不按本文实施API路线，须相应范围绑定。

C：保留订阅路线与原hard token gate，待有可验证能力后再安装双路线；现有输入工程checkpoint保留，无商业视觉请求。Parent不自行使用未知broker参数、估算字符数或订阅model默认上限解除gate。

本文具体设计只覆盖A；没有并行fallback/provider选择器。

## Explicit Route and Credential Contract

ImageTask backend保持codex，profile显式为api-bounded；backend/profile/model/effort必须在seal、route config、receipt中一致。旧Codex diagnostic或subscription profile不能自动转入本路线，不改变Kimi worker/deep及旧project schema。实际requested model继续显式冻结；没有模型升级或别名猜测。

唯一新authenticated destination为TLS api.openai.com，POST /v1/responses。Relay仍在Docker network-none中以invocation-local Unix broker socket及固定loopback channel交接；未知host/path/method/query/redirect/工具request零wire拒绝。旧subscription endpoint不作为备用路径，也不接受OAuth/account-token注入本profile。

复用现有provider-private credential loader/redaction、broker capability、ReceiptStore及installation owners，新增OpenAI credential类型的验证分支，禁止第二套credential store。Parent只加载用户明确提供的应用独立private regular owner-only reference；Key、可选organization/project identity仅存在host broker的TLS headers，不进入runtime env/argv/prompt/mount/normal receipt或错误。Runtime仅持opaque capability。不给本模型增添host/project auth访问；不读取global Codex auth，不登录、刷新、购买或开户。

真实API Key/有效account额度/授权cost evidence不存在时为INCOMPLETE，零API model调用；不要向用户要求把Key发到聊天。授权不能由caller boolean、模型自述或配置文件存在代替。

## Native Projection and Hard Generation Mapping

Native app-server仍运行在固定0.154.0 binary及全新Docker image，fresh ephemeral context、tools=[]、原PNG、原system/task输入及全部现有native/OS边界保持。实现独立版本化映射codex-image-api-cap/v1：broker在校验原native请求后，仅增加max_output_tokens=sealed generation_tokens；Native本身未发送cap的事实与映射后实际authenticated body分别保存SHA/原bytes。若native已发送字段，只能与冻结值精确相同；缺省或静默削减/提升均拒绝。

该机械映射不能更改model/effort、text/instructions、image data/count/order/identity、tools、上下文、store或路由；其他native固定framing必须有明确allowlist和conformance。发送前再次核对实际上游body的完整binding与max_output_tokens，范围/额度检查通过后才发请求。只配置原ignored config key不能算修复；禁止把visible文本截断、token估算、wall/idle cap或终态usage当预先hard generation cap。

API验证status、authenticated model/request关联、usage、max_output_tokens与terminal完整性；output_tokens包含reasoning等，超过sealed cap、缺必需proof、工具输出、incomplete/error/unknown都撤销并隔离，不能接受部分JSON。Native turn/item必须绑定thread/turn IDs并有成功turn.completed后才可能交付strict JSON_OBJECT/v1；捕获请求或turn/start响应均不算成功。

## Lifecycle and Qualification

复用原image supplement完整execution/revoke/drain/cleanup、immutable raw/canonical receipts、late quarantine、dependency失效、router-owned probe及对应envelope政策；当前未实施的image_run/image_qualification/native completion owners仍须真实实现，不以本修订存在作完成。没有successful source semantic/admission issuer或产品consumer。

新tuple显式绑定api-bounded、fixed endpoint、API credential fingerprint、mapping/native/image/broker/policy SHA、actual模型和视觉envelope。旧text/project/diagnostic/subscription qualifications不能继承。先完整native fake/OS，再有限router-owned live visual probe；typed qualification仍ROUTE_CAPABILITY_ONLY、source semantic NOT_EVALUATED、authority=none、eligible=false。

## Finite Billing Authorization

批准A同时同意这是独立API计费路线，工程实施/受管安装授权不再被误读为订阅额度。仅当全部准备条件成立，允许沿用原最多Kimi/Codex各一次、合计两次capability model requests，generation每次≤2048、wall≤180/idle≤90、原payload/output上限；不新增请求、不自动retry/fallback。其中新增OpenAI API probe的授权费用上限为USD1.00；Kimi沿用原有限预算与账号额度门，未知actual cost仍为null，不将未知计作0。不自动购买、充值或提升额度。

OpenAI probe在生成调用前必须有Parent冻结的actual payload与保守cost upper bound、当前price/source/date及已授权account额度证据；其bound必须≤USD1.00，且account余量满足；Kimi预先满足原token/request与当前quota条件。无法证明OpenAI input/image accounting和price/额度上界则零请求INCOMPLETE。已发但usage/cost未知保留null并停止，不能恢复预算或填0。费用上限不能由事后实际usage核对替代。无额外付费服务调用或token-counting/model-generation请求用于试探budget。

正式holdout成本批准仍独立；当前formalCostAuthorizationUSD=0未被本文提升，formal requests仍0。本文不改变18场景coverage、A/B/joint逐actor硬指标、零容忍false EMPTY、null政策、real-media分层或production资格。

## Verification and Installation Gate

批准后Native Codex自动用writing-plans更新已有implementation plan，在current working tree实现，无worktree/push。默认tests无商业调用。验证真正的cap注入前后等价/篡改/工具/身份/endpoint/credential leakage/old schema、完整turn/strict output、所有预算、正常/失败/取消/late cleanup、receipt类型与依赖失效；显式Docker native/fake与containment，fresh pytest/ruff/diff checks。

新host credential/TLS boundary有可信关键泄露/越权路径；stable candidate先native verification，再按base G2进行一个受管read-only Kimi deep adversarial review及Parent裁决，遵守三轮上限，失败不fallback；不默认叠native reviewer。无有效required review不能宣布engineering complete或安装可运行路线。

通过工程门后仅specific-path commit，再由官方installation owner安装clean source snapshot，核验installed source/entry/Skill/binary/image pins、原routes及installed CLI/native conformance；绝不直接修改installed tree或wrapper。不用package installation证明live route可用。全部条件满足才执行上述两次capability probes；正式受控qualification再满足Jianji全部独立准备门，PRODUCT_DISABLED及所有production BLOCKED保持。

## Self-Review

本修订只改变Codex端点/认证/计费和明确generation字段映射；原图片、context/OS、no-tools、budget最大值、生命周期、ReceiptStore、review/installation及语义门保持。区分native原body和实际API body、工程安装与视觉资格，未把API文档当本机live证明。A/B/C互斥，只有A接受本文；没有未知endpoint、占位成功、credential迁移、model/provider fallback或自动追加费用。批准前不实施新route，旧失败和accepted bytes不改写。
