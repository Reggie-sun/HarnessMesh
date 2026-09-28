# Image Route Blocker Repair

## Authorization and Boundaries

2026-09-29 用户为 Jianji M5-D2A 要求“修复blocker”，随后明确选择“包含 router 扩展，保留 sealed contract、Docker 和资格门”。该授权包含本仓库的 bounded route extension和受管安装；没有无限付费、provider切换、host执行绕过、source admission或产品activation。

新增image task/native adapter/broker/资格类型会扩展accepted semantics，按base Spec V3先准备 [image route design](../superpowers/specs/2026-09-29-image-only-route-design.md)。Self-Review已完成，SHA=`c1169a61ba8573a2c4ce442b321683a65b800230d3e8620e069e388a6d97c0f1`，`EXACT_SHA_APPROVAL_PENDING`。用户批准的是扩展范围，不伪称该新exact bytes已获批准；新image runtime semantics尚未实施，视觉probe和Jianji正式holdout请求均0。

本文记录等待上述approval期间，现有accepted contract下独立可修复的FINAL_REPORT工具响应拒绝缺陷。该bug修复不改变TaskContract、image schema、provider或旧五字段report。

## Reproduction and Root Cause

当前未修改source baseline运行 `/home/reggie/micromamba/envs/ai-video-p2/bin/python -m pytest -q`：2 failed/313 passed/20 skipped。两个失败是 `test_reporting_refuses_tool_response_even_when_upstream_ignores_removed_tools[False/True]`，分别为完整JSON和SSE响应；原测试要求HTTP502/TOOL_POLICY_VIOLATION，实际得到HTTP200。

缩小原复现：同pytest执行 `tests/contract/test_budget_reporting.py -k refuses_tool_response`，2 failed/8 deselected。没有改变这些测试或service fixtures来取得green。

`transport/broker.py::Handler.do_POST` 已在准入时把reporting phase记入owned observation的 `budget_phase`。后续诊断反复将局部 `phase` 赋值为ADMISSION_RECORD/UPSTREAM/RESPONSE_VALIDATION，原响应校验使用 `allow_tools=phase != 'FINAL_REPORT'`，因此在响应校验时永远允许tool_use。修复只读取 `observation.get('budget_phase')`；没有FINAL_REPORT时保持原路径，FINAL_REPORT拒绝tool_use/server_tool_use。

CodeGraph当前服务固定在Jianji，查询本仓库绝对broker路径返回File not found；未把该结果当调用关系证据。Root以实际source核对reporting_request→owned observation→validate_response和project_run→Broker→DockerSandbox；结构映射只辅助，不猜测未索引路径。

## Verification

显式读取并执行 `superpowers:verification-before-completion`。修复后全量offline：315 passed/20 skipped（5.64s）；全量 `--native-conformance --containment-conformance`：333 passed/2 skipped（55.41s）。其中既有Docker project/native测试真实验证Read-positive、host proc/credential Read/Bash/Task/MCP拒绝、source drift guard、报告/截断、generation cap与receipt；上游全部local fake，商业模型请求0。

两个skip为需要explicit环境的通用container与Gemini containment测试。另从已安装sandbox.json读取非secret image/runtime SHA，仅在测试subprocess设置ROUTER_SANDBOX_IMAGE/ROUTER_SANDBOX_RUNTIME_SHA256后，单独通用container test通过（1 passed）。Gemini新增路线不在本次范围，其环境特定conformance未补跑，不宣称已更新Gemini资格。`ruff check src/agent_subagent_router/transport/broker.py`及git diff --check通过。

原system Python没有pytest、所选micromamba Python没有ruff；使用已安装的router interpreter和standalone ruff后实际完成验证，没有安装依赖或改conda环境。native/conformance测试开始和结束source未改。47-file implementation snapshot SHA=`9861606f015abb5a972a003a959f2fd0d414c186da2443eaed535ba53f347aa1`，broker SHA=`7f7e51135fff144dfb139dcd90dad85a55846a8bd1e57947b5591b2a82aff2b2`。

## Managed Mapping and Parent Risk Decision

本次受管Kimi worker/high只读mapping contracts.py/project_claude.py/cli.py，seal=`6d6918d940146296cf663c3cf72484993de481d3c8cfdac3ddd61bed2d2c50f8`，invocation=`5208fa9e-fdb5-4c2f-bd84-aabf15bf8cb7`，qualified route=`27ba7e0c-32b1-41a9-8210-4f49474e0a30`。Parent机械核验全部Read/source SHA、所有artifact SHA/size、Dockerqualification、两个实际api.kimi.ai/k3-256k/high HTTP200、generation4096、55.72s/exit0/无截断；report SHA=`91b06ed5ca427028420bd23d91d0944cc8c221f3e9334a2d8805a68d24c0aa27`。这是mapping，既不是视觉probe，也不是final adversarial review或Spec approval。未接触Jianji holdout/truth。

在上方native verification后，当前一行reporting修复的G2为 `KIMI_REVIEW_NOT_REQUIRED`。用户未要求review该snapshot；修复收紧既有响应拒绝条件，不新增credential/storage/network/path/write/authority；旧错误交付后的native Read仍限sealed /work，host proc/credential/Bash/Task/MCP均有实际拒绝证据，没有证据证明此修复存在关键级泄露/越权/难恢复状态损坏路径。JSON/SSE否定测试和完整native/containment回归已证明所改边界；该bounded修复没有同时成立的重大后果、残留实质验证缺口与review独立增益。

此决定不沿用到未来Codex credential/broker/relay/image implementation；该candidate必须在其native checks完成后重新按G2独立判断。mapping报告不替代required review。

## Installation and Remaining Work

当前修复已offline/native verified；受管安装证据另追加到本文，只使用installation owner，不直接改wrapper/已安装目录，不改旧receipt。新image route尚未实施或安装、visual capability NOT_EVALUATED；实际Kimi provider不能称为AnthropicClaude。

批准新exact Spec后自动写实施plan，实施image seal/native adapters/broker/typed qualification，执行finite independent probes。只有两条真实视觉路线和caller全部提前冻结条件满足，Jianji才能继续其受控qualification；此仓库record不签发M5-D2A PASS或生产authority。若能力、身份、隔离或预算门不成立如实INCOMPLETE，不追加模型请求直到通过。
