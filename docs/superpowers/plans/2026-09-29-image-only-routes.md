# Sealed Image Input Routes Implementation Plan

## Goal

实现独立、无文件工具、Docker 隔离的 Kimi/Codex 图像传递与实际 wire proof，为 Jianji M5-D2A 解除工程路线 blocker。Router 只签发 capability evidence；不获得 source semantic、admission 或产品 authority。

## Scope and Authority

Native Codex Parent 执行并裁决，使用 current working tree，不创建 worktree、不 push。用户“那继续实现啊”批准 [image Spec](../specs/2026-09-29-image-only-route-design.md) exact SHA `c1169a61ba8573a2c4ce442b321683a65b800230d3e8620e069e388a6d97c0f1`，批准 owner 为 [architecture-spec-acceptance.md](../../records/architecture-spec-acceptance.md)。Base architecture SHA `a3c216c077608767e1ac7ac7d03869e8d90f49256469691e8206c71edbf3566c` 继续约束全部执行。

既有 TaskContract、project adapters、五字段报告、credential/ReceiptStore、Docker 和 installation owners 保持兼容。新增 responsibility 分为 image contract/seal、native projection/wire validation、image lifecycle/qualification，禁止将其塞入 project worker 或建立第二 ReceiptStore。

2026-09-29 用户随后“批准”接受 [Codex API amendment](../specs/2026-09-29-codex-image-api-budget-design.md) exact SHA `14e10cad0f3afc44f0f3796c2ae86c45e161c8a17ab2d54801c8c261a81df272`，由同一acceptance owner绑定；本文按writing-plans更新并Self-Review。以下API repair milestones替换M3中的subscription credential/endpoint semantics，其他未完成milestones继续执行，不创建第二plan或workflow。

## Current and Target Behavior

当前只能通过 project 文件工具读取输入，无合格图片入口，Codex 无受管 relay/backend。目标为 `inspect-images`、`run-images`、`qualify-image-route`：strict image-only contract → immutable private PNG seal → capability admission → source=None Docker native invocation → authenticated request/response → typed canonical receipt。未知 runtime framing、工具等价禁用或模型身份均 fail closed；运行配置和模型自述不能替代证明。

## Contracts and Invariants

- `ImageTaskContract` 单独 schema `image-task/v1`，显式 backend/model/profile/effort、accepted refs、system/task text、ordered PNG descriptors、匿名 metadata、`JSON_OBJECT/v1`、`FRESH_SEALED_INPUT/v1`、finite image budgets。旧 Budgets 不扩上限。
- `image_contract.py` 提供 strict parser 和 safe regular PNG reader；`image_seal.py` 提供 private immutable manifest/bytes 创建和验证。只返回匿名 model-visible identity，source path 不进入 native 输入。PNG header/chunk CRC、无动画、完整 compressed pixel stream、尺寸/长度/SHA 与 descriptor 一致；相同像素不同 identity 保留顺序。
- `adapters/image_claude.py` 复用 no-tools Claude primitive，native stream-json stdin；`adapters/image_codex.py` 构造 app-server JSON-RPC fresh thread/turn。不得带项目 constitution/Skills/reporting notice。全部 runtime/image/config pins 必须入 seal；runtime capability 不成立时 UNSUPPORTED_REQUIRED_CAPABILITY。
- `image_wire.py` 在真实 upstream 前比对 native system/task/metadata、model/effort/no-tools、ordered decoded PNG 及预算；未知文本/改图/漏图/加图/工具定义零 wire 拒绝。明确机械映射独立版本化。
- `transport/broker.py` 与 `permissions/docker.py`/`container_entry.py` 保留原默认，仅提供受限 image validation hook、payload bounds 和独立 Codex fixed endpoint channel。新 `transport/codex_broker.py` 复用现有 credential/redaction/lifecycle owners，真实 token/account 只在 parent 固定 TLS 使用。
- `image_run.py` 复用 Docker、supervisor、ReceiptStore：所有结束先 revoke/drain/cleanup，再 final receipt；未知/超限/取消/late 输出隔离，不能交付成功；费用未知为 null。
- `image_qualification.py` 使用同一 ReceiptStore，kind `image-route-qualification/v1`；旧 qualification ID 无法升级。tuple 绑定全部依赖、实际 native/OS/live evidence 和测试 envelope。任意变化失效。
- Probe 输入由 router 独占生成、预冻结 rubric；8 张随机无文字图案含首中末和同像素不同 identity。最多 Kimi/Codex 各一请求，总两请求；generation≤2048、wall≤180、idle≤90，no retry/fallback。额度未核验零请求 INCOMPLETE。8 图不能推出 648 图或真实媒体泛化。
- Jianji 全程 PRODUCT_DISABLED；human method/schema/session 不变，不触及 source identity/knowledge/admission/product lifecycle，不接触 holdout truth/recipes。

## Ownership and Dependencies

Parent 拥有计划/批准/阶段记录、broker/relay、native adapter、CLI、image execution/qualification、安装和最终判断。可分配 named `bounded_worker` 仅写 `image_contract.py`、`image_seal.py` 及对应 unit tests；其余 writers 不碰此四路径，writer 不 commit、不 nested delegate、不访问凭据/holdout/provider。已有 readonly `code_mapper` 可聚焦 Codex native protocol 与实际 tool disable 控制。受管 Kimi deep 独立读取最小精确 source 范围作安全调查，seal 至 receipt 核验期间不修改其 frozen paths。

## Major Milestones

### M1: Strict Input and Immutable Seal

新增 `src/agent_subagent_router/image_contract.py`、`image_seal.py`，测试 `tests/unit/test_image_contract.py`、`test_image_seal.py`。独立 parser、bounds、accepted refs、PNG integrity、symlink/race/growth 拒绝、ordered multiplicity 与 immutable artifact seal。封存后修改输入或 manifest 必须拒绝，不能仅以 caller digest/boolean 作证明。

Acceptance：adversarial unit tests 真正通过；旧 schema tests 仍拒绝 image fields。seal/artifacts owner-only，manifest 字段严格，descriptor path 不出 native projection。

### M2: Kimi Native Image Transport and Wire Guard

新增 `adapters/image_claude.py`、`image_wire.py`，按现有 owner 修改 `transport/broker.py`。native stream-json 输入原字节 PNG；actual HTTP 前逐项绑定并保存 private raw request/response hash。project budget reporting 与 image 禁工具策略分离；旧 request/model/effort/default limits 不变。

测试新增 `tests/unit/test_image_wire.py`、`tests/conformance/test_image_claude.py`；fake upstream 包含 wrong model、extra framing/text、首中末缺失/重排/改图、工具与 generation truncate negatives。Acceptance：本地 fake 实测原 PNG hashes 与 no-tools 控制，非 config 存在证明；无商业调用。

### M3: Codex Isolated Backend and Authenticated Channel

新增 `adapters/image_codex.py`、`transport/codex_broker.py`、`codex_image_wire.py`，最小修改既有transport credential owner的OpenAI API Key分支。仅app-owned private API credential reference；runtime opaque capability；固定TLS api.openai.com POST /v1/responses，不接触global auth，不登录/刷新。独立helper/process使用bounded native RPC，fresh ephemeral thread，无持久状态、ambient instructions或通用工具。

`codex-image-api-cap/v1` 在exact native system/task/anonymous metadata、image字节/order/multiplicity、model/effort/tools=[]与已证明framing校验后只增加max_output_tokens=sealed generation_tokens；已有cap必须精确相同。保留native原bytes与实际API bytes/hash，不把ignored config当proof。Strict response events须绑定响应ID/model/request ID、完整completed status、usage≤cap和无tools；incomplete/unknown/truncation拒收并revoke。Native stdout另证thread/turn/item关联及turn.completed，单纯POST capture不交付。

现有container_entry.py与project Docker入口保持原bytes/默认8MiB限制；新增bounded `permissions/image_container_entry.py`仅复用其固定relay/安全执行机制，将image入口注册/v1/responses及32MiB限额。DockerSandbox新增显式image-entry选择、校验wrapper与base entry labels，原default入口/pins行为不变。`scripts/build_image_route_sandbox.py`只用已有local pinned binary/base image、network-none构造新的Kimi/Codex image配置，不替换旧配置或wrapper，不下载或更新native版本。

测试 credential injection/redaction、wrong endpoint/path/redirect/model/response association、native tool attempts、fresh context；运行显式 Docker fake conformance。不能证明 runtime 全部等价禁用/身份即 typed unsupported/INCOMPLETE，不接受伪成功。新 immutable runtime image 仅 installation/build owner 管理。

### M4: Canonical Image Lifecycle and Capability Qualification

新增 `image_run.py`、`image_qualification.py` 与 CLI 三个入口，复用 ReceiptStore、supervisor、Docker cleanup；unit tests 覆盖 qualification 类型混用、依赖/envelope 失效、零 wire admission refusal、取消/超限/迟到 quarantine、strict JSON output 与真实 finalization。

Probe generator/rubric 与任意 caller task admission 分离。bootstrap 只准 router-owned probe；native/OS 证明不足或预算/额度不明时零商业请求。完整 manifests/raw HTTP/raw model/canonical output/invocation provenance 记录 null 与 NOT_EVALUATED。Actor/caller 不能签发资格。

### M5: Verification, Review, Installation and Finite Probes

fresh full offline `python -m pytest -q`，受影响 `--native-conformance` 与 Docker containment、ruff、diffcheck。按 base G2 在 stable exact candidate 判断一次：新 credential/broker/relay critical 泄露/越权路径触发一个 managed readonly Kimi deep/max review；封存 exact SHA/Spec/Plan/verification，Parent adjudicate，每个 semantic fix 后验证及适用 re-review；三轮上限，不叠 native reviewer。

仅完整满足工程门后 specific-path commit、官方 installation owner 安装 clean source snapshot、核验 installed source/entry/runtime/image pins，重跑 installed CLI/conformance。真实账户额度、预算、native/OS 条件全成立才各一次 capability probe。任何失败停止并保留历史；无追加请求换取通过。工程候选、installed、capability-only、正式语义资格分别记录。

### M6: Jianji Readiness Handoff within the Same Task

只更新 `docs/shape-matched-cover-m5d2a-plan.md`、`docs/shape-matched-cover-m5d2a.md` 当前 owners，将实际 typed route receipts 与 inputPlan/config/budgets 匹配。两 actor isolated context 与全部冻结证据/正式总预算不足则 INCOMPLETE，不启动 formal run；若全成立按原 AI Spec 执行而非再请求“继续”。所有硬错误停止政策和逐 actor 指标保留；产品下一阶段不自动授权。

## Completion and Verification

先读取 current `verification-before-completion` discipline，再对当前可解释 snapshot 做真实验证；不把 unit/fake/HTTP200 当图片能力或语义资格。Router records/status 保存每一阶段证据，Jianji AOCI 若有自身受管理源码改变则按现有 owner 维护；foreign mixed AOCI ownership conflict 明确记录，不能覆盖他人条目。无 whole-repo对齐证据不宣称全局对齐。

## Current Execution Checkpoint

新API amendment已按用户“批准”绑定，generation blocker进入implementation。Native mapper仅read-only核对credential/broker/receipt/Docker integration owners；独立bounded writer拥有 `transport/credentials.py`、`transport/codex_broker.py`、`codex_image_wire.py`及其三个unit tests，Parent拥有native adapter、image relay/Docker/runtime build、image lifecycle/qualification、CLI及对应tests/docs。集合不相交。Writer不得处理global auth/holdout/truth、调用Provider、nested delegate或stage/commit；先运行focused red再实现。此分工减少critical TLS/wire边界与native completion耦合的context负担；Parent最终核对安全路径、source diff和原生验证。

Live OpenAI请求前还必须有真实private credential reference、account额度和actual frozen payload的保守input/image token accounting及current price/date/source，cost bound≤USD1；缺任一为零请求INCOMPLETE。新增费用批准不授权credential自动发现/迁移或formal预算；probe失效/未知不补请求。工程安装不等于capability qualification。

M1 已实施并通过离线否定测试。M2 已有独立 native PNG projection、精确请求校验、禁工具响应和 raw exchange hook；真实 Docker/fake 验证 worker/deep 的八图及拒绝行为，但尚无 live invocation owner、32 MiB broker admission 或视觉 capability receipt，不能写成整条 M2 完成。

M3 的 pinned Codex 0.154.0 已在独立 Docker diagnostic image 内证明原 PNG 顺序、fresh user-only 输入和实际 tools=[]；其实际请求即使配置 `model_max_output_tokens=2048` 仍无生成上限，`IMAGE_GENERATION_BOUND_UNPROVEN` 为当前可复现 blocker。Diagnostic helper 只捕获 fake 请求，不证明成功 turn、真实视觉能力或额度。没有读取账号凭据、调用真实 Codex、建立 authenticated broker/relay 或替换现有安装。

M4–M6 仍未完成。当前 CLI 仅新增无商业调用的 `inspect-images`；没有用占位 `run-images`、`qualify-image-route` 或成功 issuer 绕过预算门。独立 probe=0、formal requests=0、所有 source semantic 指标 NOT_EVALUATED。范围内 input-only engineering checkpoint 保存源码和实际测试，完整工程/安装/资格继续 INCOMPLETE。详细证据、Risk Gate 与剩余工作由 [record](../../records/image-input-engineering-2026-09-29.md) 独占。

## Self-Review

已逐段覆盖 accepted Spec 的输入/seal、原字节传递、native framing、凭据隔离、真实 identity、finite lifecycle、typed receipt、probe rubric/envelope、拒绝/旧 schema 兼容、安装及风险审查。文件职责与名称一致；无占位步骤。未成立的 runtime/账户/预算门是真实执行门，计划不填造结果。此计划 Self-Review 通过后返回 Native Codex 实现，无新增 plan approval gate。

## API Candidate Checkpoint

上述input-only描述是历史checkpoint。用户“批准”已接受API amendment exact SHA `14e10cad0f3afc44f0f3796c2ae86c45e161c8a17ab2d54801c8c261a81df272`，Parent与独立six-path writer已实现M3/M4工程candidate：新fixed TLS broker/only-cap mapping、private application reference拒绝global auth、实际native thread/turn/item与strict JSON、image-only Docker wrapper、canonical invocation/probe/conformance/qualification receipts及CLI。旧project Budgets/entry/runtime配置不变。

实际新image的source=None OS及完整八图native/fake通过；新Codex framing按pinned UUIDv7/window及原PNG确认，实际terminal summary与user input分开验证。Fresh offline524 PASS/27 explicit skip，完整native/fake+containment548 PASS/3 skip，ruff/diffcheck通过。Probe reservation按host canonical state固定，不能用新task或新--state恢复请求；只允许router-owned probe，formal USD0零请求，tested envelope不扩到648帧。

构建中真实发生临时最后tag删除原Kimi image登记；已由原BuildKit记录与OCI各blob SHA恢复完全相同的08ef image，旧config/receipt未改。Builder改为保留verified base alias，新增untagged-base/alias-conflict否定测试。恢复不被当作新qualification。

M5当前为KIMI_REVIEW_REQUIRED，native verification后进入exact stable snapshot的一个managed read-only deep review；尚未宣布工程完成或安装。新视觉provider请求0；缺独立OpenAI API credential reference、当前额度/冻结accounting evidence时capability与M5-D2A均INCOMPLETE。本聊天/订阅登录不是api-bounded credential。具体evidence、review与安装状态由 [API engineering record](../../records/image-api-engineering-2026-09-29.md) 独占，后续按真实结果更新同owner，无需再请求“继续”。

## Required Review Blocked Checkpoint

M5第一轮managed Kimi review已真实执行；canonical invocation `5d46f112-ba0e-48ae-afa0-10b2b1640d9a`为OUTCOME_UNKNOWN，第二次上游attempt TLS_ERROR/CONNECT，缺完整report/verdict。Parent核验canonical artifacts与封存源码未变，未采用部分工具探索，未自动retry/fallback。review round1失败保留，gate未满足，official installation BLOCKED；当前source保存未验收engineering checkpoint不表示M5完成。M6只更新Jianji phase/plan和真实证据，capability/formal请求保持0；有效review、clean安装、installed验证及真实账户/预算门仍为remaining work。具体失败和归档由同一record独占。

用户随后“安装”，Parent在调查round1、核对源码未变及取得当前TLS-only成功证据后，显式封存并执行一次round2；scope/安全门不变。第二轮invocation `dbd52980-2e47-4b06-9ff3-f6609a89a90f` HTTP200后RESPONSE_BODY连接中断，canonical OUTCOME_UNKNOWN，无完整report。M5安装门仍BLOCKED、official installer未运行；不自动使用剩余第三轮、不恢复预算或用partial结果通过。两轮历史保留，最新evidence和remaining work仍由同一API record独占；M6/视觉/正式资格保持INCOMPLETE。
