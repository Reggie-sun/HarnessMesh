# HarnessMesh Architecture Spec Acceptance

## Status

`ACCEPTED_SPEC_WITH_USER_DIRECTED_Q2_AMENDMENT`

2026-09-26 用户在获知本地 Deep entitlement 的 24 小时自动过期规则后，明确要求“开子代理把这个路由策略去掉不要有限制”。当前 Q2 据此作一处窄修订：取消 observation age 的上限，保留有效非未来时间戳、account/credential/context 证明和依赖失效条件。此次执行授权直接来自当前指令；不伪称用户重新逐字批准了整份 Spec 的新 SHA。修订后的 SHA-256 为 `a3c216c077608767e1ac7ac7d03869e8d90f49256469691e8206c71edbf3566c`，实施证据见 [entitlement-age-limit-removal.md](entitlement-age-limit-removal.md)。

用户在收到新 written Spec 的 exact path 与 SHA-256 后，于 2026-09-23 明确答复“批准”。该历史批准只绑定下列 exact bytes，不覆盖上方修订；上方修订依赖另行明确的用户变更指令。其余未来 semantic revision 仍按 Spec 的 `V3` 与 `G1` 执行。

## Original Accepted Artifact

- Canonical Spec path: `docs/superpowers/specs/2026-09-23-harnessmesh-rare-review-design.md`
- SHA-256: `ff18503d3099f16d18947cc56a983b942aed6567dd61573beed24a3634fe8d5c`
- Source commit: `67da77c32330cede94147aec7176ec26cb0fa6db`
- Source tree: `5070d8f2f279156e6f2721f528be0526573caa03`
- User approval recorded at: `2026-09-23T21:47:34+08:00`

## Previous Accepted Snapshot

旧版 `docs/superpowers/specs/2026-09-19-harnessmesh-architecture-design.md` 的 SHA-256 为 `9f732140424db3a96772f115ec0ff2ef212b525822d6593de95be561777f6203`，用户批准记录时间为 `2026-09-23T20:21:50+08:00`。旧版 bytes 保留为历史证据；本次批准后不再是当前 canonical Spec。

## Acceptance Boundary

本次 acceptance 只确认上述 exact Spec snapshot 已通过 `superpowers:brainstorming` Architectural flow、Spec Self-Review 与 User Review Gate。Spec 内的 “draft”/“user review pending” 是批准前封存 bytes 中的历史 metadata；当前 acceptance 状态以本记录绑定的 path、SHA-256 与用户批准为准。依照该 Spec 的 `G1`，Spec 默认不调用 Kimi review；未执行 Kimi Spec review 不是缺失 gate。

本记录不接受或声称任何 Implementation Plan、runtime implementation、refactor、push 或 release，也不把 Spec acceptance 解释为 implementation completion、qualification 或 project-native verification PASS。

## Accepted Image Route Supplement

2026-09-29 用户先明确选择“包含 router 扩展，保留 sealed contract、Docker 和资格门”，随后在获知 image-only route written Spec 的 exact path/SHA 和尚未实施状态后要求“那继续实现啊”。该指令批准并授权执行已展示的下列 supplement；不是此前已实施或 qualified 的证明。

- Path: `docs/superpowers/specs/2026-09-29-image-only-route-design.md`
- SHA-256: `c1169a61ba8573a2c4ce442b321683a65b800230d3e8620e069e388a6d97c0f1`
- Approval source: 当前用户继续实施指令，绑定上述前一窗口已展示的 unchanged bytes。
- Base contract: 上述 current accepted architecture Spec；新 mode 不放宽旧 project worker schema、工具或 authority。

Supplement 内 `DRAFT / EXACT_SHA_APPROVAL_PENDING` 是批准前 frozen bytes 的历史 metadata；当前批准由本记录独占绑定。授权包括 implementation planning、受限实现、native/fake/containment 验证与符合冻结条件的最多两次独立 capability probes。它不批准无限商业调用、正式 Jianji semantic qualification 的未冻结预算或产品 activation。

## Accepted Codex Image API Amendment

2026-09-29 用户在收到新API修订路径、exact SHA及新增计费边界后明确回复“批准”，按前一回复推荐A批准实施及受管安装。绑定 `docs/superpowers/specs/2026-09-29-codex-image-api-budget-design.md` SHA `14e10cad0f3afc44f0f3796c2ae86c45e161c8a17ab2d54801c8c261a81df272`；原frozen文件的DRAFT/approval pending为历史metadata，bytes不变。本窄修订明确覆盖image supplement的Codex subscription transport为新增 `api-bounded` profile/fixed OpenAI Responses API/API Key与单字段generation cap映射；旧profiles不自动迁移。

新增OpenAI capability probe最多一次、费用上限USD1，并须原spec所有native/OS/真实credential、actual payload、cost upper bound与已授权account额度证据成立；Kimi仍最多一次，两条合计最多两次，不retry/fallback。正式holdout cost authorization=0，production授权未扩大。该批准接受Spec并授权范围内implementation planning/execution/verification/review/installation，不证明代码已完成、live能力或source semantic资格。

## User Directed Engineering Review Fallback

2026-09-29 用户明确要求“修改逻辑,当kimi一直出问题的时候得用原生子代理”。该新授权仅修订 base §9 及 API amendment 的 engineering reviewer 限制：连续两次真实受管 Kimi 运行故障无完整输出时，按照 `/home/reggie/.codex/SUBAGENTS.md` 的 Repeated Kimi Failure Fallback，由一个职责匹配的 read-only native Codex reviewer 接手同一候选审查，Parent 仍须核实全部 findings 与 verification。不是删除 required review，也不是声称用户事先批准本段的新 SHA；执行授权来自这条明确变更指令。

旧 accepted Spec bytes 与两次 OUTCOME_UNKNOWN receipts 保留原样。安全/权限/预算/资格拒绝、源码漂移或 reviewer 硬错误不能充当故障触发。Native 身份与执行证据独立记录，不伪称具有 Kimi Docker/route receipts；任何 semantic fix 仍须新 snapshot、验证及适用 re-review。当前两次 invocation `5d46f112-ba0e-48ae-afa0-10b2b1640d9a`、`dbd52980-2e47-4b06-9ff3-f6609a89a90f` 的 transport 故障满足本条阈值，下一步执行 native 工程审查而非第三次付费 Kimi 调用。

Image actor/provider、sealed contract、qualified route、Docker containment、canonical image receipts、有限 capability 费用及 formal budget=0 保持。安装仍需有效 required engineering review 与 Parent 裁决；本修订不批准生产、source admission、视觉资格或使用本聊天充当 blinded actor。

## User Authorized One Extra Native Review

2026-09-29 Parent在三轮native预算用满后，已完成NR-IMAGE-005分段通路修正、601项工程验证及exact review package，并明确请求“仅增加一次同一原生reviewer的只读复核，通过现有门后继续安装”。用户紧接回复“继续完成任务”，按该具体待确认动作授权额外一次有界native re-review。原三轮历史不删除或重置，本次为round4/extra1of1；没有追加Kimi或视觉/付费请求。使用同一named read-only `reviewer_max`，Scope/Authority/Boundaries、Parent裁决、required verification及clean官方安装门不变；无有效复核仍不可安装。这不是无限审查预算，也不补齐缺失API credential/account/cost或生产授权。

## Task Bounded Repair Authorization

用户随后替换global instructions：已明确任务内所需共享契约、有限预算及恢复规则变更由Agent自主评估、记录、实施和验证，不再逐项请求批准。Parent据此Self-Review本任务工程修复：保留Kimi两次与native四轮全部历史，为NR-IMAGE-005剩余reasoning/失败响应边界分配最多两次同一read-only `reviewer_max`复核（累计round5、round6，各wall上限900秒）；不按改snapshot重置计数。用完仍未满足门则真实记录阻碍。该窄修订优先于base Spec §9与SUBAGENTS的默认三轮升级询问规则，不取消fresh verification、exact snapshot、Parent裁决或无unresolved blocker安装门。

Self-Review：Scope仍仅image route的凭据/响应持久化工程修复、其否定测试和安装；scanner归属transport，ReceiptStore/lifecycle/credential owner不变。失败或不可完整验证的响应只保留hash/长度/分类；已验证的正常原始wire证据不改变。原冻结Spec bytes不重写，验收标准不降低；未知结果不重试，旧输出不升级；真实视觉各一次/总两次、OpenAI USD1、正式预算0、凭据保护和生产禁止仍为用户明确保留的上限。

## Interleaved Output Repair Continuation

权限实际恢复后，round5原thread已不在runtime列表，原dispatch无可用报告、执行/费用未知，历史不重置。Parent以同一named read-only `reviewer_max` profile的新thread执行剩余round6（164 frozen paths前后一致）。NR-IMAGE-005/006/007由具体交错reasoning、Kimi native文本替换、HTTP failure诊断分段泄漏触发；Parent真实5 failed/2 passed确认，随后另两项reasoning关联负例确认。不是为取得赞同而追加审查。

依当前任务内默认授权，Self-Review后增加**仅一次**round7 full engineering re-review、wall900秒，保留Kimi2次/native1–6全部历史；只有这次修复验证通过才dispatch，不能切回Kimi或重置次数。修复将独立SSE stream重组与reasoning terminal关联置于raw捕获前，两backend统一native/upstream文本摘要绑定；HTTP失败不再保存body派生诊断，保留status/typed分类及quarantine摘要。此前“脱敏诊断保留”是未完整安全修复的历史candidate，当前这处窄兼容变化替代它；原project请求/schema/report/工具准入不变。

Source/ReceiptStore/credential/qualification/lifecycle owners保持；Self-Review覆盖正常交错reasoning、匹配Kimi输出、失败status、全套native/OS/旧project回归与官方clean安装门。若round7仍有blocking findings，先调查真实触发，不自动续跑。无新视觉/付费或formal授权，所有产品禁止保持；原accepted Specs frozen bytes不重写。

## Protocol Block Repair Continuation

Round7在157/157未漂移snapshot上仅剩NR-IMAGE-005：Kimi同一block的start/delta被event type分开，以及未验证response_id可人为分组；NR006/007无剩余具体触发。Parent实际ReceiptStore否定测试4 failed/2 passed确认；额外unknown-index3 failed/6 passed证明image block关联仍不足。调查后修正scanner只采用对应协议字段：Kimi按统一block family/index，忽略Codex专用字段；Codex按已验证message/reasoning part身份。原image wire owner另校验start唯一顺序index、delta类型/开放block及完整stop，拒绝无start/已关闭/非法type，不改旧project协议。

依任务内默认授权Self-Review，增加仅一次round8 full read-only `reviewer_max`复核、wall900秒，前1–7轮和消费不删除、不重置、不因有效finding切provider。Parent先验证实落盘quarantine、正常start/delta、不同block、unknown metadata/index及全套native/OS/旧project回归，再封存dispatch；无unresolved blocker才官方clean安装。Self-Review确认未新增owner、Provider请求或formal/产品授权，原Spec bytes保持。该扩展有新的可复现安全触发依据；若仍失败先调查，不自动无限续跑。

## Protocol Payload Repair Continuation

Round8在155/155一致snapshot上发现NR-IMAGE-005的具体剩余路径：第二条thinking_delta额外嵌套aux.thinking，污染只按叶名拼接的实际thinking流。Parent真实ReceiptStore否定测试2 failed/10 passed确认，随后修正同一scanner owner：协议payload单独重组，通用递归保留完整JSON路径，列表同字段仍按顺序聚合。辅助同名字段不进入协议流，原正常wire/raw与metadata-only quarantine边界保持。

依任务内默认授权Self-Review，增加仅一次round9 full read-only `reviewer_max`复核、wall900秒；Kimi2次/native1–8全部历史及消费保留，无预算重置或Provider切换。Parent先验证nested credential/capability/clean及既有incomplete/error/HTTP quarantine回归，再运行全套offline/native/OS/Ruff/diff并封存，最后无unresolved blocker才clean官方安装。Self-Review确认只修可复现输入流边界，不增加owner、真实请求、visual/formal预算或产品权限；原Spec bytes保持。该有限复核基于新证据，不以取得赞同或机械扩轮为目的；仍有finding则先调查真实触发。

## Typed Semantic Payload Repair Continuation

Round9在155/155一致snapshot上发现NR005的signature_delta附加thinking字段仍可污染实际thinking流。ParentReceiptStore否定测试真实2 failed/13 passed确认，并主动核对同根因JSON typed content：text part的非语义thinking可混入其他thinking parts，实际red2 failed/16 passed。当前修正按content_block.type/delta.type精确选择协议语义字段；通用JSON路径包含typed part身份和不可与字符串key碰撞的array标记。保留正常thinking/signature/JSON流及metadata-only quarantine，不拒绝正常附加metadata或改变旧project合同。

依任务内默认授权Self-Review，仅增加一次round10 full read-only `reviewer_max`复核、wall900秒。全部Kimi2次/native1–9和真实消费保留，不重置、不切Provider。Parent先完成typed SSE/JSON的credential/capability/clean实落盘与既有否定回归，再执行fresh full/offline/native/OS/Ruff/diff；封存后才dispatch，无unresolved blocker才clean官方安装。Self-Review确认修复仍在唯一scanner/receipt/wire owners，scope、安全门、已批准visual各一次/总两次、OpenAI USD1、formal0和产品禁止不变。该有限追加有独立可复现根因证据；若仍发现新触发先调查，不自动无限续跑。

## Initial Semantic State Repair Continuation

Round10在156/156一致snapshot上发现NR005：Codex added reasoning summary或created/in_progress output预载前段，后续仅后段仍可通过终态关联。Parent实际ReceiptStore三位置credential/capability/clean red9 failed/9 passed确认；主动核对Kimi同根因message_start预载thinking，red3 failed/18 passed确认。当前在两既有image wire owners要求空初始语义状态：Codex created/in_progress output及added reasoning summary为空，Kimi message_start content为空。后续完整delta/done/terminal proof保持；无法绑定的prefilled状态拒绝、仅存quarantine，不改旧project validator。

依任务内默认授权Self-Review，仅增加一次round11 full read-only `reviewer_max`复核、wall900秒，Kimi2/native1–10全部历史及真实消费保持。先fresh完整验证与实落盘否定回归，再封存dispatch；无unresolved blocker才clean官方安装及installed conformance。Self-Review确认收紧image初始状态关联属于当前可复现泄漏修复，保持唯一owners、accepted Spec bytes、原预算/credential保护/零formal及生产禁止。不是无限追加或寻求赞同；新finding须先调查真实触发，不能绕门安装。

## Semantic Field Shape Repair Continuation

Round11 在156/156一致snapshot上发现NR-IMAGE-005：Kimi start/JSON语义字段及Codex terminal-only reasoning summary可携带array/object前段与string后段；scanner路径分开，畸形响应仍获raw持久化。Parent在冻结集合外用实际ReceiptStore复现30 failed/15 passed，确认该具体触发后才改源码。修正在既有image wire owners收紧typed semantic field形状：Kimi text/thinking/data及存在时signature为string；Codex summary为list、part为summary_text/string，存在时encrypted_content为string。正常string及辅助metadata保留，不扩scanner特例、不改旧project协议。

按当前任务内默认授权Self-Review，仅增加一次round12 full read-only `reviewer_max`复核、wall900秒。Kimi2/native1–11全部历史与实际消费保留，round11 findings不抹除；先实落盘red-green及fresh完整offline/native/OS/Ruff/diff，再封存新snapshot并dispatch。无unresolved blocker才clean官方安装及installed dual conformance。Self-Review确认是已复现凭据持久化边界的有界修复，source/ReceiptStore/qualification/lifecycle owner、accepted Spec bytes、visual各一次/总两次、OpenAI USD1、formal0、生产禁止均不变。若有新finding先调查，不自动追加请求或重置轮数；结果仍由既有API record承接。

## Reasoning Content and Nullable Metadata Repair Continuation

Round12 source前后165/165一致，材料绑定修正仍同一900秒预算，不重写原157-path manifest。NR005暴露Codex terminal/initial reasoning.content和同item added/done encrypted_content的具体分段raw路径；NR008暴露新增string-only检查误拒绝合法encrypted_content:null。Parent实际ReceiptStore 19 failed/7 passed确认；nullable依据当前OpenAI primary SDK定义，摘录与源SHA随新snapshot封存。修复terminal reasoning_text/string形状及空initial content、已opened reasoning必须done；opaque encrypted字段按已验证同item身份重组known secrets，保留正常opaque string及absent/null。仍用既有image wire/scanner/ReceiptStore，不新增owner或改旧project合同。

按任务内默认授权Self-Review，仅一次round13 full read-only `reviewer_max`复核、wall900秒，保留Kimi2/native1–12全部历史/原错误及消费。先完整fresh offline/native/OS/Ruff/diff与实际持久化拒绝/nullable/opaque兼容验证，再封存包含当前原日志及primary摘录的snapshot。没有unresolved blocker才clean官方安装和installed dual conformance；不把工程修正或review当真实视觉资格。Self-Review确认该有限追加基于新可复现安全与兼容根因，全部accepted Spec bytes、finite visual各一次/总两次、OpenAI USD1、formal0、凭据及生产禁止不变；仍有finding先调查，禁止自动循环或预算重置。最新结果由既有API record独占。

该修复候选首次full native实际754 PASS/1 FAIL/2 skip：既有grandchild断言只接受Z而观测X，随后只读确认已reaped；Linux primary proc API和kernel state mapping确认X为dead。只修该test接受Z/X，仍立即拒绝R/S/D等存活状态，不增加观察window、修改supervisor或放宽wall/cleanup预算。原失败日志保留，修正后fresh串行完整验证及本轮snapshot包含这一明确test ownership。

## Initial Reasoning Shape and Identity Repair Continuation

Round13 前后178/178一致，Parent因已确认新NR005触发要求提前结束，实际170.423秒；未完成全部full scope，不具有full review clearance，不返还轮次或抹除原预算。Parent实际ReceiptStore首先6 failed确认initial encrypted_content array/object前段漏检，再17 failed/3 passed确认同根因及boolean/integer item ID的Python equality混淆。修复在既有`codex_image_wire.py`抽取同一私有reasoning shape校验，统一用于added/done/JSON及SSE terminal；所有output item身份为nonempty string，消除类型相等但canonical scanner分组不等的漏洞。合法absent/null/opaque string和辅助metadata继续允许，既有scanner与receipt owner不变。

按任务内默认授权Self-Review，仅新增一次round14完整read-only `reviewer_max`复核、wall900秒。Kimi2次/native1–13全部历史、失败、partial scope及消费保持；先fresh full offline/native/OS/Ruff/diff及实落盘red-green，再封存实际当前日志dispatch。仅最新full review完成且Parent裁决无unresolved blocker后clean commit、official installation和installed双路线conformance；不把提前结束或tests PASS作为clearance。Self-Review确认修复没有第二owner或旧project合同变更，accepted Spec bytes、visual各一次/合计两次、OpenAI USD1、formal0、凭据与生产禁止不变。该有限新增仅基于新的真实根因证据，不允许自动循环或改写旧qualification。

## Native Input Capture Repair Continuation

Round14完整关键scope在186/186一致snapshot上实际完成（672.329秒），仅剩NR005：Codex `_forward` 在map/admission/preflight前保存未经校验的native raw，跨instructions/input.text的secret前后段虽400/零upstream仍落盘。Parent在冻结集合外用实际ReceiptStore red3 failed确认后修复：非法mapping只存classification/SHA/length；合法native raw移至active/request预算、current seal/pins/probe preflight都成立后，与actual request捕获相邻。现有ReceiptStore、broker、token/account/lifecycle与旧project owners不变；没有恢复预算、发送Provider请求或新增重试。

Self-Review按当前任务内默认授权仅分配一次round15 full read-only `reviewer_max`复核、wall900秒，保留Kimi2/native1–14全部历史及消费。该变更涉及凭据持久化安全，按base G6执行full re-review；此前Parent的targeted建议未采用。复核可复用同reviewer亲自检查、且新snapshot hash不变的独立模块证据，但须重新检查changed capture/map/preflight/receipt call path，并真实覆盖完整关键scope，不能把旧full report当新结果。先fresh full offline/native/OS/Ruff/diff及实落盘否定/正常wire正例，再封存dispatch；最新required full review和Parent裁决没有unresolved blocker后才clean commit、官方安装与installed双路线验证。Accepted Specs bytes、visual各一次/合计两次、OpenAI USD1、formal0及全部生产禁止保持；若出现新触发先真实调查，不自动改预算或绕gate安装。
