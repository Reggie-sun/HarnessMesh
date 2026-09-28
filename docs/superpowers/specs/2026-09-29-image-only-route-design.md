# Sealed Image Input Routes

## Status and Authority

`DRAFT / SELF_REVIEWED / EXACT_SHA_APPROVAL_PENDING`。2026-09-29 用户为 Jianji M5-D2A 明确授权“包含 router 扩展，保留 sealed contract、Docker 和资格门”。该授权允许准备此扩展及独立工程验证，不伪称尚未形成的本文件已经获 exact SHA 批准。

本文是 [canonical architecture Spec](2026-09-23-harnessmesh-rare-review-design.md) 的新增 image invocation contract；base accepted SHA 为 `a3c216c077608767e1ac7ac7d03869e8d90f49256469691e8206c71edbf3566c`，acceptance owner 为 [architecture-spec-acceptance.md](../../records/architecture-spec-acceptance.md)。原 C1/C4/P2–P4/E1–E5/Q1–Q4/V1–V3/G1–G9 继续适用；本文只为独立 image mode 明确输入、native projection、output protocol 与 qualification policy，不改变 project worker/writer 的权限或五字段报告。

按 base V3：新 exact bytes 批准前不得实施本文新增 runtime semantics。批准后自动使用 `superpowers:writing-plans` 编写 durable plan，并在已授权范围执行；不以 plan、commit 或安装完成替代实际资格。Native Codex 保留执行、风险裁决和 completion owner。

## Goal and Non-Goals

提供可审计、无文件工具、隔离的 Kimi 与 Codex 原尺寸图像输入路线，使调用者能验证实际发送图像、真实上游身份、独立上下文及有限生命周期。Router 只证明运行/输入/路线能力，不判断图像语义是否完整，也不签发 Jianji source knowledge、admission 或 semantic qualification。

不新增 provider 自动选择、fallback、retry、登录/刷新 token、全局 Codex credential 读取、产品 activation、host runtime 执行、项目 mount、worker tools、Skills、AGENTS 加载或 nested delegation。Gemini 与既有 routes 不纳入本扩展。正式 holdout 和全部 truth 留在 Jianji author owner，不进入 router 测试或 delegated review scope。

## Source-Led Findings and Approach

当前 `contracts.py` 的 TaskContract 未定义 image fields；`project_claude.py` 强制 Read/Glob/Grep 和实际 Read/report，不能充当无工具盲审路线。`adapters/claude.py::build_invocation` 已有无工具、禁 hooks/MCP/config/历史、fresh directories 的 primitive，可为独立 image adapter 复用。`DockerSandbox.execute` 支持 source=None；broker、supervisor、ReceiptStore 已有各自 owner。

Jianji `ChatGPTSession.completeUsing` 的 native app-server RPC 能运输 `{type:"image", url, detail}`，但该产品会话、baseInstructions、credential launch 与工具禁用测试不能直接证明本路线。Router `runtime_config.py`、container relay 与 upstream broker 当前无 Codex backend；这是新增 native adapter、relay allowlist 和 authenticated upstream proof 的边界。

采用独立 `ImageTaskContract`、image execution adapter 和 typed qualification。另两种方案——将图片塞进 project goal 再允许 Read，或直接在 host 调用产品/CLI 会话——会失去 image payload 和隔离证明，拒绝。扩大旧 TaskContract 的权限/五字段报告会影响现有拒绝行为，也拒绝。

## Image Task and Seal Contract

新增明确的 `inspect-images`、`run-images`、`qualify-image-route` CLI namespace；现有 inspect/run/receipt 命令和旧 schema 保持兼容。`receipt` 继续读取同一 ReceiptStore，按 kind 区分新记录，不能将普通 route-qualification 自动提升为 image-route-qualification。

ImageTaskContract 是 strict versioned schema，未知字段拒绝。只包含 taskId/parentSessionId、明确 backend/model/profile/effort、accepted Spec/Plan refs、原样 system/task text、按顺序排列的 image descriptors、调用者允许的匿名 metadata、outputProtocol、finite budgets 与 context policy。backend 仅显式 kimi 或 codex；model/effort 不能推测、默认换名或由 worker 选择。没有 readPaths/writePaths/commands/Skills/tools/credential fields。

Image descriptor 在 parent 控制区绑定本地 regular PNG file 的 byte length/SHA-256、width/height 和调用者的 opaque imageId。路径只用于 seal/materialization，不进入 model-visible text、runtime filesystem 或 native tool input。拒绝 symlink、非 regular、越界增长、duplicate imageId、非法 PNG、尺寸不符、动画和 digest 失配。相同 PNG bytes 可以拥有不同 imageId，必须保持 multiplicity/order。

独占 private contract store 保存实际 PNG bytes、manifest、ordered imageIds、input/prompt digest、context policy、budgets、adapter/runtime/policy fingerprints 和 accepted refs。run 只能消费 immutable seal，不能接受 caller boolean 或外部临时 JSON 作为 seal/资格证据。PNG 不缩放、裁剪、重编码或降采样；data URL/native base64 是可逆 transport representation，actual image bytes 必须逐张与 seal 一致。

硬资源上限：单 task imageCount 1–1024、总 PNG bytes≤24MiB、native payload≤32MiB、每张≤4096×4096、prompt text≤256KiB、canonical output≤8MiB。具体 invocation 必须预先选更小或相同的有限值并绑定；这些实现上限不等于已经 qualified 的视觉 envelope。只有实际通过 conformance/probe 的更窄 tuple 可准入。

Context policy 为 `FRESH_SEALED_INPUT/v1`：每个 invocation 创建 fresh runtime/home/config/cwd，不恢复 native session。需要跨 packet 目标目录的调用者，只能把本 actor 先前已冻结目录作为下次 sealed 的允许 text；不能继承作者聊天或对方结果。Mapping stage 可以在 caller 双份原 receipts 冻结后运输显式选择的双方声明与原图，但 router 不拥有该阶段的 semantic admission。

## Native Projection and Isolation

Kimi 使用 pinned Claude Code native stream-json 输入，image content blocks 直接经 stdin 交给 runtime；`--tools ''`、空 setting sources、strict empty MCP、禁 hook/plugin/memory/session persistence、no chrome 与 no retry 均属于 frozen adapter，不调用 project adapter。

Codex 使用 pinned `@openai/codex` executable/version/binary SHA 与 app-server JSON-RPC native image input，fresh ephemeral thread，no environments/no model-visible repository instructions。使用 native settings/thread/turn controls禁止 shell、exec、搜索、apps/MCP、skills/multi-agent 和网络工具。配置存在不算 native proof；fake upstream 发出的 tool attempts 必须被 runtime 拒绝或被独立执行层阻断，不得执行。若本 pinned runtime 无法证明所需等价禁用能力，返回 UNSUPPORTED_REQUIRED_CAPABILITY，不在 prompt 中声称禁用。

两者只在现有 DockerSandbox 中执行：source=None，无 project/home/auth/recipe/truth mount；read-only root、non-root、dropped capabilities、no-new-privileges、private proc/IPC、network none 与 bounded tmpfs/pids/CPU/memory。只允许 invocation-local broker socket 与已封存运行输入。新增 Codex image 按安装 owner 生成并核验 runtime/image digest，禁止依赖 host ambient configuration 或直接修改安装目录。

Container relay 明确注册 Codex 固定 loopback provider URL，与现有 Anthropic/Gemini paths 分支隔离。不准入任意 endpoint、URL 参数代理、DNS fallback、redirect 或通用 socket 代理。不得给 no-tools image task 注入 project constitution、file/report notice、other actor state 或可见 source paths。

## Credential and Authenticated Transport Contract

复用 provider-private reference loader、broker capability 和 redaction owner。Kimi 的实际 key 仅由 host broker 加载。Codex 只接受 parent 明确提供的应用独立 credential reference，例如 Jianji app-owned auth storage；不读取或修改 `/home/reggie/.codex/auth.json`，不登录、不续 token、不复制 credential 给 runtime。

Codex broker 读取授权 reference 的 owner/mode/regular file，校验 access token/account association，保存 private fingerprint；真实 token/account secret 只在固定 TLS `chatgpt.com/backend-api/codex` 上游使用。Runtime 只持 invocation-local opaque capability，在已固定 local provider transport channel 使用。argv、日志、prompt、normal receipt、tools、mount 和异常均不能泄露 key、token、account secret 或 capability。

每次 upstream request 发送前校验 actual native model/effort、tools empty、system/task projection、允许 metadata、PNG base64 decode 后的 count/order/length/SHA、prompt/context/transport limits及剩余预算。接受 runtime 的固定 native framing 必须有版本化明确 allowlist 和 fake conformance，不能忽略未知 system text 或默默覆盖 model/effort。任何缺图、首中末遗漏、额外图片、重复 identity、改图/缩图、工具定义或未经封存文本都零 wire 拒绝。

分别验证 actual upstream response 的 status、model identity、request/response ID、completion/usage 和 no tool calls。Codex provider 若只提供部署别名而无不可变 revision，如实记录 authenticated endpoint declaration 及最强实际稳定身份，冻结适用 envelope；不把 UI model 名称或 self-report 当 proof。实际原始 HTTP request/response 与 normalization version 保存在 private supervisor artifacts，normal receipt 只给绑定 digest/observations。没有可靠 model/request association，INCOMPLETE/IDENTITY_UNVERIFIED。

不复用 project reporting_request 的探索/收尾 prompt 变换。Kimi profile/model native transform 如需保留，必须独立版本化、仅显式声明的机械 transport 映射；变换前后 bytes/hash 均记录，PNG decode hash不变。模型 max_tokens/effort必须实际与 sealed generation policy一致。

## Output, Lifecycle and Receipt Contract

Image mode 的独立 outputProtocol=`JSON_OBJECT/v1`：保留完整 UTF-8 原始 model text，解析为一个 strict JSON object，拒绝 duplicate keys、truncation、tool calls、额外 prose、markdown repair 或非 object。Router 不解释 domain fields，不补 UNKNOWN/EMPTY，不重问到 parse 成功。旧 project E5 五字段 envelope 不适用于此明确 mode，但原 routes 继续要求 E5。

Invocation 复用 E1 的 SEALED→ADMITTED→RUNNING→STOPPING→FINALIZED；所有结束路径都先 broker no-new-work/revoke、bounded drain/unknown、container/process cleanup，再冻结 receipt。Late response 保存为 quarantined artifact，不能成为 accepted output。取消、wall/idle/request/payload/generation/output 超限、supervisor loss或未证实 cleanup均单独记录，不能给 completed/qualified。

Canonical `image-invocation/v1` receipt 仍由 ReceiptStore 独占签发，绑定 seal、qualified tuple、fresh context/image/directory identity、actual payload/PNG manifests、authenticated observations、raw/canonical output、过程/撤销/cleanup、预算/usage/cost及 artifacts。caller 和 model不能签发、恢复或升级 receipt。字段缺证据为 null/NOT_EVALUATED；actual cost未知不填0。

调用者明确签发的整包预算 ledger 可以关联多个 invocation；每个子请求仍消费其 sealed budget，并在下一请求前校验剩余整包额度。Router 不把新 invocation 当作授权补充请求，不拥有 Jianji formal run lifecycle；Jianji controller仍须冻结本轮总预算并阻断迟到输出和语义硬错误。

## Qualification Policy

新 `image-route-qualification/v1` 是 route capability-only 记录，复用 canonical ReceiptStore/qualification evidence，不建立第二个 store。它绑定 backend/model/effort、credential fingerprint、runtime/image/adapter/broker/policy/input/output protocol SHA、实际测试的 PNG数量/尺寸/byte/context envelope、native conformance、OS containment、live probe、issuer与依赖失效条件。

Admission 必须已有对应 tuple 的 native fake conformance 和无项目 mount 的 OS containment。首次 live capability probe 是显式 `PROBE_ONLY`：只接受 router 自己构造并预封存的非项目、非 holdout probe 输入及 rubric；不需要已成功的 image live qualification，但不继承普通 text smoke 成功。Probe route admission 和 project data admission 分开，不能借 probe 输送任意用户图像。

Probe 使用随机非文字视觉图案：8张原尺寸 PNG，首/中/末与相同像素不同 identity均覆盖，位置/颜色/形状由 private rubric 预冻结，prompt不泄露答案。绑定 PNG native delivery 和 deterministic JSON rubric结果，不接受“我看到了图片”self-report。Probe检测有限视觉运输与辨认能力，不检测全片贴纸穷尽性，也不作为 M5-D2A 真值资格。

本修复阶段 live probe 上限为 A/B 各一次、合计最多2个 authenticated model requests，每次 generation≤2048 tokens、wall≤180s、idle≤90s、payload≤32MiB、output≤1MiB；不自动重试、换 provider/model或追加讨论。Probe实际费用未知记录null；调用前由 parent 核验其明确有限 token/request授权与当前账号额度边界，不自动购买、刷新额度或支付。正式 holdout 整包成本/请求上限不由此授权，需要 Jianji spec 要求的另行提前冻结条件。

任一路线无真实图像支持、身份不明、隔离/native proof不成立、输出/rubric失败、额度不明确或 budget超限即 NOT_QUALIFIED_CAPABILITY/INCOMPLETE，停止该能力流程，不追加 probe直到通过。旧 probe失败永久保留；修改方法后不能沿用旧 tuple，须另行授权新的有限 probe。

通过该有限 probe 后仅可签发对应视觉 envelope 的 `ROUTE_CAPABILITY_ONLY`；source semantic qualification仍 NOT_EVALUATED。扩大图片数量/尺寸/context、换 binary/image/adapter/broker/policy/protocol/model/effort/credential identity 或配置依赖变化使证据失效。不能从8图 probe推断648图 mapping可用；Jianji实际 inputPlan 超出 envelope时 INCOMPLETE。

## Verification and Acceptance

默认全部 offline：strict schema/old schema拒绝行为、seal byte binding/PNG negatives/opaque metadata、source path不泄露、credential注入与redaction、wrong-model/redirect/extra text/tool请求、generation/payload/request/wall/idle上限、duplicates保留、取消和正常结束的 revoke/drain/late-output quarantine、receipt类型混用与dependency失效。

Native conformance 显式使用本地 fake upstream，逐 backend验证 actual image blocks/PNG hash、系统 framing、全部工具禁用、fresh home/thread/session、stdout协议和真实进程退出；没有商业请求。Docker adversarial tests证明host项目/secret/proc/network/root/filetools不存在或不可访问，broker capability不会进入输出。

安装只使用现有 installation owner：source snapshot和entrypoint pin核验、生成新 isolated runtime image、smoke CLI schema、旧 qualified routes不可自动继承新 adapter/policy的证据。既有 source installation与historicalreceipts保持原字节，不patch host claude/codex或直接编辑wrapper指向目录。

在 stable implementation checkpoint 先运行完整 offline pytest、受影响 native/containment regressions，再按 base G2 判断一次 Implementation Review Risk Gate。新 credential/broker/relay边界的可信 critical泄露/越权failure path触发一个受管 Kimi deep/max adversarial reviewer；review绑定exact candidate、accepted本文SHA/Plan、verification和sealed receipt。Spec/Plan只Self-Review，不额外派 reviewer；若原资格因安装变化失效，先满足其门，不绕过审查。

工程完成要求代码/安装/原有路线回归与适用 review gate真实满足。视觉 capability通过另有 typed evidence；两条路线和完整原始发送/响应证明均具备后，Jianji才能继续自身正式资格准备。缺任一条件如实记录 INCOMPLETE；不宣布 M5-D2A PASS、不启用产品。Router持久记录在 docs/records与implementation-status，Jianji phase/evidence仅更新其既有M5-D2A owners。

## Self-Review

已核对新增mode对C1/C4/E5的显式扩展、旧schema/工具/报告兼容、native而非giant prompt、broker credential owner与实际TLS身份、无项目mount和无truth/peer输入、seal与actual PNG对应、类型隔离/资格依赖、finite probe与正式预算区分、正常结束/取消/迟到隔离、旧失败保留、native先行Risk Gate及安装owner。不把单元测试/HTTP200/PARSED/模型一致当能力或语义验收。

本文无未知类型/占位方案；未成立的 runtime capability、Codexidentity和账号额度是明确可执行fail-closed gates，不能在实施时补造成功。Router TaskContract/profile的旧行为不放宽，Jianji human/knowledge/admission/product生命周期不改变。Self-Review完成不替代用户批准exact bytes。
