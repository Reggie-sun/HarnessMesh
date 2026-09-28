# Image API Engineering Record

## Authority and State

用户“批准”接受API amendment exact SHA `14e10cad0f3afc44f0f3796c2ae86c45e161c8a17ab2d54801c8c261a81df272`，由既有acceptance owner绑定。历史DRAFT/pending及旧失败保留。当前是native-verified engineering candidate；required review第一轮因上游TLS失败未完成，official installation因此BLOCKED，capability及Jianji M5-D2A仍INCOMPLETE，authority=none、eligible=false、source semantic NOT_EVALUATED。无source admission、产品activation或successful production issuer。

## Implementation and Verification

Parent保留native/OS/lifecycle/receipt/CLI/build/最终裁决，named bounded_worker独占credential、Codex wire/broker及三组tests，交接后Parent补reference admission。复用ReceiptStore与原Docker/supervisor，旧project入口和8MiB Budgets不变。新image wrapper禁止project/candidate mounts，32MiB只是schema/transport ceiling，不是已验证视觉envelope。

Codex api-bounded固定TLS api.openai.com POST /v1/responses，实际native原body与增加唯一sealed max_output_tokens后的body分别保存。Fresh Codex UUIDv7/window framing和userMessage原PNG/文本绑定、真实completed turn的summary output、Kimi session/no-tools及完整JSON由实际native evidence核对。Canonical receipts区分owned probe、native/OS conformance、image invocation与capability资格；旧text/project qualification不继承。Monetary reservation使用固定host ledger，不随--state/task改变恢复；缺quota、credential、current frozen input/image accounting门零商业调用。

Fresh全套offline **524 PASS/27 skip**（7.84s），显式全套native/fake+containment **548 PASS/3 skip**（66.26s），ruff与git diff --check通过。三项skip对应未配置旧Codex diagnostic以及两项Gemini native（环境条件）；新Codex/Kimi的source=None OS和完整native两项均通过。默认测试不访问Provider。程序source SHA `2d1c3976f2f37f3a48444f4d2c24d0492b13d433c323c42af90c62660434e4f8`；最终installation后须匹配当前source并再次验证。

新Codex image `sha256:93a5c2a3a96c5d55784548417f27f1259b528f00523b78032aaddafcd9e359f2`，runtime0.154.0 SHA3188814c…；新Kimi image `sha256:58c7dfa8e17612d496bb4827f5f928b3a277f271c3d4a026e4cb6b7dc0b1f0ab`，Claude Code runtime2.1.277 SHA722210f0…，实际provider依然Kimi。Wrapper SHA8448707b…；原entry SHA5fd6c690…未改。Configs为独立private文件，不替换旧sandbox.json。

## Build Incident and Exact Recovery

初次bare sha256 FROM被BuildKit当registry名拒绝，未接触Provider。修为临时local tag后构建成功，但cleanup image rm删除最后tag时也移除原未tag Kimi image08ef登记。这是本任务真实事故，不归因其他writer。

普通cache rebuild生成新attestation/index ID f807，不能代替旧08ef资格。随后通过官方BuildKit history `zu1ev4h3lslqfvjg9j510hnxz`取得原index08ef、manifest9cff、attestation manifestc54d及config1bb8，从同一cache已验证的原层和原record timestamps/invocation恢复原attestation layer d6ed；逐blob SHA完全相同后OCI load，Docker inspect再次返回**原完整08ef image ID**与原runtime/entry labels，旧config和所有historical receipts原字节保持。没有改变旧qualification的pins或以新image冒充原image。Builder已删除image rm cleanup，保留verified deterministic base alias并拒绝alias冲突；新增两项regression通过。旧Kimi doctor实际20项containment检查qualified=true。

## Review Risk Gate

stable candidate按base Spec §9为 **KIMI_REVIEW_REQUIRED**。具体failure path：新增host API credential/TLS capability及image input/native receipt之间，错误binding或权限校验可能泄露private Key、让未经授权的输入/次数进入付费端点，或将fake/不完整native结果签成capability；后果关键级。Native tests证明已测拒绝与OS边界，但独立adversarial reviewer可调查跨wire/credential/budget/receipt关联遗漏。不是因diff大小或已有agent而机械触发。

计划仅一个managed read-only Kimi deep/max reviewer；exact source/diff、accepted Spec/Plan、native/offline evidence由sealed package绑定。Parent调查裁决findings，semantic fix后fresh native验证和必要re-review；三轮上限、失败不自动retry/fallback、不加native reviewer。完成required review前不宣布engineering complete或安装可运行新路线。

## Required Review Outcome and Installation Blocker

第一轮review seal=`ec83aef7c5692a830629b22a30d28975349b1cc30ca16336aa0633bc942b9134`，qualified project route=`4f2d5dc8-4234-4665-b382-e82f1ad6cc00`，canonical invocation=`5d46f112-ba0e-48ae-afa0-10b2b1640d9a`。实际provider为api.kimi.ai/k3，deep client k3[1m]/max；有效project预算按kimi-maximum-v1为wall3600/idle1800、64 requests、generation32000、output16MiB/context8MiB，未传播到image task。封存时Plan SHA=`24eb5acd5fdd44b01626b58d8ecd1bc487a8dff4c54e6542ac181ce550f493ee`；review snapshot SHA=`b0e80acadd41ab7099770943acbce64fd98c39fd666d6009b6e279f220e7f49a`，30个snapshot路径在receipt核验前逐SHA一致。随后只更新状态文档，程序source SHA保持上述值。

canonical receipt为OUTCOME_UNKNOWN、native exit1、22.84s。两次上游attempt中，第一次HTTP200验证Kimi身份、input11166/output468 tokens并产生工具探索；第二次TLS_ERROR/CONNECT，未取得HTTP响应。不存在完整审查报告或可采纳verdict，HTTP200不替代required review。Parent核验了五个实际Read的path/range/SHA与封存源码；未将部分探索当作审查通过。orchestration_retries=0、fallback=forbidden，internal_retry_count=unknown，actual_cost=null；失败计入review round1，未自动补请求。TLS连接失败的底层原因未被此receipt证明，不宣称已修复远端网络。

据accepted API Spec §Verification and Installation，缺有效required review不得安装可运行新路线。本次保存明确未验收的工程checkpoint，既有installed package仍source_commit=`223da83ecc510b80cb062d2ac8772a7c8f13f565`、source_dirty_at_install=true；本任务没有调用installation owner或替换其sandbox配置。新两image已经本地构建并经native/fake验证，但不等于安装或视觉资格。剩余为有效完成必需review、官方clean-source安装及installed验证，再在真实账户证据成立后有限owned capability；不通过修改gate、换provider或重复请求直到通过来完成。

独占证据archive=`/home/reggie/.local/state/agent-subagent-router/image-api-engineering-20260929`，149项文件manifest SHA=`8b766b54b206d45bbcc26bf8d66ce5517eab8f05da02aaa1f32ab0d7be452e57`，保存review原始receipts/artifacts、review源码快照、full native/offline日志、两config、新image与原08ef inspect、BuildKit恢复记录及两组完整native/fake输入/receipts。这是engineering backup，不新增资格issuer、不升级synthetic结果；大型恢复tar仍留原路径。阶段记录由本owner承接，无适用专用session-capture skill；不写外部memory。

## Live Limits and Remaining Work

当前visual Provider requests=0、formal requests=0、formalCostAuthorizationUSD=0；未收到独立OpenAI API credential reference和当前额度/actual frozen accounting evidence。用户“就用codex啊”明确继续Codex，但不构成提供API Key、绕过≤2048 gate或读取global Codex登录。原subscription route无已证明hard cap的历史事实保留。

批准的OpenAI capability至多1次/USD1；Kimi至多1次，总2，每次generation2048/wall180/idle90，全部preflight真实成立才调用，不用换state/新fixture恢复预算。当前source review的648帧、独立truth/criteria/inputPlan/human协议不被本probe复制或改写。先required review与clean official install/installed verification，再有真实账户证据才owned capability；M5-D2A formal仍需自己的全部冻结/actor/receipts/correspondence/truth-vs-review gates与独立成本批准。未评估指标null，synthetic不能推出real-media PASS。
