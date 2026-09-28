# Image Input Engineering Checkpoint

## Result and Authority

2026-09-29 用户“那继续实现啊”批准已展示且未修改的 image supplement exact SHA `c1169a61ba8573a2c4ce442b321683a65b800230d3e8620e069e388a6d97c0f1`。批准由 [acceptance owner](architecture-spec-acceptance.md) 记录；Spec 中旧 DRAFT 状态保留为历史，不回写成此前已实施。自动选用 writing-plans 后已创建并 Self-Review [implementation plan](../superpowers/plans/2026-09-29-image-only-routes.md)，随后实施，而非停在 plan。

当前是 `OFFLINE_INPUT_ENGINEERING_CHECKPOINT / INCOMPLETE`。已完成独立输入边界并实际执行 Docker/native fake 验证；没有完整 image invocation/qualification owner、可信 live Codex channel 或受管新安装。真实视觉 probe=0、formal requests=0、semantic qualification=NOT_EVALUATED、authority=none、eligible=false。工程 tests 不签发 route 或 source 资格。

## Implemented Owners

- `image_contract.py`：独立 strict image-task/v1、finite budgets、匿名 metadata、ordered image descriptors、逐 component no-follow regular read、长度/SHA/dimension 绑定、PNG CRC/IDAT/zlib/pixel stream/animation 拒绝。旧 TaskContract/Budgets 不变。
- `image_seal.py`：owner-only private store，原 PNG 不重编码；immutable manifest 与有序 blob、task/pin/accepted-ref SHA 绑定，verify 拒绝篡改、额外文件、symlink、unsafe owner/mode。相同像素不同 image_id 均保留。结构 accepted 标志不代替 Parent acceptance 或 route proof。
- `adapters/image_claude.py`：复用 pinned no-tools primitive，native stream-json image blocks，清空 tools/setting-sources，独立 system/task text，不使用 project file/report adapter。
- `image_wire.py`：实际发送前严格比对 model/effort/max_tokens、系统固定 framing、允许 metadata、完整 text、图像数量/顺序/原 bytes 与 no tools；未知 framing fail closed。`require_native_generation_bound` 拒绝缺失或无效实际上游生成上限。
- `image_output.py`：独立 JSON_OBJECT/v1，不修复 markdown、duplicate keys、额外 prose、truncation 或 tool attempts；原项目报告协议不改。
- `transport/broker.py`：Parent-only request validator、response tool refusal、raw exchange callback。默认参数保持旧路径，拒绝发生在 upstream 之前。未新增 authenticated endpoint、credential loader、relay 或生产 consumer。现有 broker 的 8 MiB transport cap 未扩为新合同的 32 MiB上限，不能声称所有 image envelopes 已准入。
- `image_inspect.py` / `cli.py`：只新增无商业请求的 inspect-images，绑定实际 runtime/adapter/image/protocol/implementation pins并封存；qualified_route=null、formal_execution=BLOCKED。没有占位 run-images、qualify-image-route 或成功 issuer。
- `adapters/codex_image_rpc.py` / `scripts/build_image_codex_sandbox.py`：固定 Codex binary、独立 local image 和 bounded native RPC 的离线诊断；无真实凭据、外部请求、host project/home mount。Helper 使用固定 loopback fake upstream，捕获请求后终止；不证明生成或成功 turn。

M1 四路径由 named bounded_worker 实施，Parent已读取最终源码、验证并接收 ownership release；worker 无 commit/provider/holdout 权限。named code_mapper只读核对 app-server schema及 turn/item 关联；Parent核对其“请求捕获不是成功 turn”结论并在测试中明确拒绝此推论。无 nested delegation。

## Native Input and Isolation Evidence

Kimi实际执行在 pinned Claude Code 2.1.277 Docker内，source=None；worker/deep的8张PNG、顺序、重复像素身份、实际 tools=[]、native tool-response拒绝均通过本地 fake测试。固定SDK identity framing只是该 native protocol 文本；实际服务仍是 Kimi，不将 Claude SDK 标签写成 Anthropic视觉能力。

Codex binary 0.154.0 SHA=`3188814c35471432d4123203e0eb38e5bddc60226e3d7ddf0e59e649ea140022`。最新独立 diagnostic image=`sha256:4348c225136362d3e85d82c0251db00991950e07fd07e244acaecbd6a00fd1d9`，helper SHA=`93283e67d2c40e596389db9ee59c8b261da6082f7df99eeed925ba714852a959`。旧 Docker entry 原字节复用，无修改现有 sandbox config或wrapper。

实际有效控制为 orchestrator.skills.enabled=false、orchestrator.mcp.enabled=false、skills.include_instructions=false、tools.experimental_request_user_input.enabled=false、tools.update_plan.enabled=false，以及 include_environment_context/include_permissions_instructions/include_apps_instructions/include_collaboration_mode_instructions=false；其他 native features按helper固定关闭。早期仅配置 features.orchestrator_skills/tools.orchestrator_skills 无效，实际仍注入 skills/request_user_input，历史捕获保留。最终fake请求实际 tools=[]、instructions精确为冻结system、仅一条user message，首中末与8图原SHA/顺序一致，末图与首图同像素但未去重。没有把配置存在当禁用证明。

## Proven Generation Blocker

该 pinned native request没有 max_output_tokens/max_tokens；设置 model_max_output_tokens=2048 后实际 wire仍无上限。八图 native测试验证此事实，并确认 IMAGE_GENERATION_BOUND_UNPROVEN 拒绝。合同要求 probe generation≤2048 且实际有限预算可证实；wall/idle/output上限不能冒充生成token上限。

此诊断fake固定403并在收到请求后结束，不证明真实 provider model、额度、视觉辨认、终态turn.completed或最终JSON。真实身份、费用、视觉rubric和source语义均 NOT_EVALUATED/null。添加未证明受支持的 broker 参数、切换 provider、使用host或放宽预算都不能解除此门；需要实际支持且经固定协议/身份/预算证据验证的路径。

v1–v8历史offline build/capture保存：初始容器argv路径拒绝、未知配置无效/超时、错误bool替代struct导致config拒绝、tools/context残留、最后工具和context清空但generation bound缺失。不改写为全部成功。这些仅本地fake诊断，无付费视觉重试。

## Managed Kimi Investigation

按 external-subagent Skill的 sealed contract/qualified deep route/Docker/canonical receipt执行独立只读安全mapping，限定 Docker owner和entry两文件，不接触holdout/truth或账号内容。Seal=`bdbfe78cc4bd3f52b8a06ca9ac9a967af10d4ad436b44dab7605bebadd37944a`，qualification=`4f2d5dc8-4234-4665-b382-e82f1ad6cc00`，invocation=`fcef80d3-1a7f-4c6c-a394-cfacef10c3ba`。有限wall240/idle120/request2/generation4096；实际2次api.kimi.ai / k3 / max HTTP200，137.48s，exit1/UPSTREAM_GENERATION_LIMIT、orchestration_retries=0。

Parent机械核对canonical artifact SHA/size与两个Read源SHA。第二请求截断，无可接受最终报告；未采用其findings，未自动补调用，也不将HTTP200当图片能力。该mapping不是 implementation review或正式actor，失败与 receipt永久保留。预算分别记录：本工程mapping实际请求2、真实视觉probe0、正式qualification0。

## Fresh Verification

Source/test/script 113路径开始与结束SHA完全相同，snapshot digest=`2e5b8b0ad8afac70efd92a5517bccb780a8d62e11f3bacbc7de0d6b310b61b65`。Python使用 /home/reggie/micromamba/envs/ai-video-p2/bin/python；ruff使用 /home/reggie/.local/bin/ruff。

| Check | Actual result | Boundary |
| --- | --- | --- |
| Full offline pytest -q | 397 PASS /25 skip，5.24s | native/containment显式关闭，无商业调用 |
| Full --native-conformance --containment-conformance | 420 PASS /2 skip，55.68s | 显式Codex v8 config；generic/Gemini显式环境tests未启用，不宣称它们完成 |
| Kimi image native subset | 4 PASS，3.75s | Docker/local fake、8图worker/deep及工具拒绝 |
| Codex image native subset | 1 PASS，1.19s | 8图/no-tools实际请求及生成上限缺失拒绝 |
| ruff check src tests scripts | exit0 /All checks passed | 当前全部Python源码 |
| Source CLI inspect-images | 两backend各封存8个distinct ID，随后verify通过 | 仅匿名synthetic PNG；qualified_route=null，零商业请求 |
| Jianji typecheck /affected tests | exit0；4 files /86 tests PASS，23.45s | AI工程与human media回归；无语义资格 |
| git diff --check | exit0 | 最终文档仍在交付前再核对 |

## Implementation Review Risk Gate

对上述 exact input-only snapshot应用 base §9 G2，结果 KIMI_REVIEW_NOT_REQUIRED。条件1：用户要求实施，没有明确要求review本snapshot。条件2：当前无new credential loader/authenticated endpoint/relay、live consumer、成功issuer或production/durable-state迁移；broker新增hooks仅可信Parent选择，旧默认关闭，现有api key仅在旧owner内，测试覆盖旧响应/拒绝路径。输入CLI只写自身exclusive private store、不覆盖源文件；Docker source=None隔离及工具负向证据没有当前可通往关键凭据泄露、跨项目authority或难恢复生产状态损坏的具体路径。条件3：生成预算/真实视觉/最终turn缺口已有具体fail-closed证据且阻断所有live调用，不以审查替代 capability gate；未发现本离线切片另有重大后果和仍需独立review弥补的语义缺口。Parent已最终源码/diff核对及项目原生验证。

此判断只适用于未安装的input-only工程checkpoint，不能为未来Codex credential/broker/relay/lifecycle实施预授review豁免。完整工程completion当前仍BLOCKED_CAPABILITY；若后续新增关键凭据/authority路径，按相应stable candidate重新调查并触发一个受管Kimi adversarial review，不叠加native reviewer。本次失败Kimi mapping绝非final review。

## Durable Evidence and Remaining Work

Private独占目录 /home/reggie/.local/state/agent-subagent-router/image-input-engineering-20260929 保存60项日志、任务、native历史capture/config/build、start/end source map、Kimi canonical receipt、Spec/Plan snapshot及实际CLIseal。Manifest SHA=`63626da93666721b0ccc305b3a735afdda2b55462e0aa1f1fe7ffd14cc4c8e47`；schema明确 engineering-only，authority=none、eligible=false。不建立第二个ReceiptStore或签发image qualification。

稳定checkpoint只提交本任务路径，不push、不worktree、不安装部分路线。已安装bba0563源码保持原字节，旧qualifications不升级。

下一步必须解决或实际证明Codex generation预算；再实施受管authenticated transport、完整native终态/output关联、image supervisor/receipt/qualification owner、32MiB受限运输及router-owned预冻结rubric。完整native/OS/credentials/额度/预算/review门满足后才official install与最多两次真实capability probes。8图probe只签对应envelope，不能推出648图mapping能力。Jianji随后还需匹配两actual routes与完整inputPlan、正式成本授权、可信execution/mapping/correspondence/issuer和独立truth-vs-review运行；这些未完成时持续INCOMPLETE。

Jianji与生产authority不变：PRODUCT_DISABLED、M5-B/M5-C/M5-D3/M5-D4及verified-no-sticker production issuance BLOCKED。human资格未改。受控qualification即使未来通过也不自动授权生产。
