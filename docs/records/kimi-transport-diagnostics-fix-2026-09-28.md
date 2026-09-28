# Scope And Evidence

Session `01a0e70e-c709-7021-b3cc-1515bbbf5f65` 的 invocation
`257feaa6-3fea-4744-9796-4a5c5dab00af` 在约 8.8 秒后失败，只有一个 wire request。
native report 为本地 gateway 的 `502 {"error":"OUTCOME_UNKNOWN"}`；receipt 未保留
上游 HTTP 状态或底层异常，零 observed_reads。不能断言 Kimi 服务直接返回 HTTP 502。
历史信息无法追溯恢复，不回写该 receipt，不将它计作独立审查完成。

# Owner And Contract

`transport.diagnostics` 独占安全异常分类，`KimiUpstream` 标记实际执行阶段，
`Broker` 将诊断写入既有 per-request observations。替换吞掉 generic exception 的
旧路径，不添加第二个 receipt owner。原有 RouterError 分类、OUTCOME_UNKNOWN、
runtime 502 error envelope、model/effort、预算、无 fallback/retry 与验收边界保持。

新增可选 `transport_error`/`broker_error`，仅含固定 phase/kind：TLS_SETUP、CONNECT、
REQUEST_SEND、RESPONSE_HEADERS、RESPONSE_BODY、RESPONSE_METADATA 或 broker 的
ADMISSION_RECORD、UPSTREAM、RESPONSE_VALIDATION、DELIVERY；类别包括 DNS_ERROR、
TLS_ERROR、TIMEOUT、CONNECTION_ERROR、INCOMPLETE_RESPONSE、HTTP_PROTOCOL_ERROR、
OS_ERROR、UNEXPECTED_ERROR。阶段来自 control-plane 常量，不来自模型或异常消息。
不记录 exception text、动态 class name、traceback、partial body、headers、路径或 credential。
上游响应头已收到但 body 读取失败时保留真实 http_status；未收到状态时不补造。
这些诊断不表示请求没有送出、远端没有执行，也不授予 retry 或 acceptance。

# Verification

修复前新增 suite 26 failed、1 passed，复现原始异常直接抛出/诊断缺失；修复后：

- `micromamba run -n ai-video-p2 python -m pytest -q tests/unit/test_transport_diagnostics.py tests/unit/test_transport_activity.py`：34 passed。
- `micromamba run -n ai-video-p2 python -m pytest -q tests/contract/test_transport.py -k 'request_route_must_match_every_field or response_identity_is_upstream_not_cli or missing_model_or_request_id_is_unverified or sse_final_usage'`：12 passed、10 deselected。
- `micromamba run -n ai-video-p2 python -m pytest -q tests/unit/test_receipts.py tests/unit/test_protocol.py tests/unit/test_evidence.py tests/unit/test_project_run.py tests/unit/test_generation_budget.py tests/unit/test_installation.py tests/regression/test_minimax.py`：72 passed。
- `git diff --check` 通过。118 项通过。阶段/错误测试为 fake HTTPSConnection；broker
  tests 在无 listener 的情况下调用真实 HTTP handler，覆盖准入、发送、分类、publication、
  脱敏与真实 HTTP error 区分。此 seam 不是 native/OS containment qualification。
- 测试证明 exception `__str__` 不被访问；敏感 body/message 不进入诊断；已知控制错误
  不变；一次失败不追加 upstream call。未进行真实 Provider 调用或全套 socket/native 测试。

# Risk Gate And Delivery

Stable candidate 为本记录所在 implementation commit；changed paths 为 broker.py、
diagnostics.py、test_transport_diagnostics.py 与本记录。适用 accepted Spec E4/P4/G2；
durable implementation Plan 不适用。

KIMI_REVIEW_NOT_REQUIRED：用户要求修复而未要求该 snapshot 的新增 Kimi review；
此变更仅增加由可信层生成的可选诊断，不改变 route/grants/credential delivery、unknown
classification、重试或 acceptance。未发现 critical 后果，也未发现重大后果、剩余实质验证
缺口、Kimi 独立增益同时成立的证据；反例测试覆盖秘密输出与错误身份/证据准入不变。
Standing delegation 按 external-subagent Skill 进行 doctor preflight，结果为
BLOCKED_CAPABILITY / SANDBOX_IMAGE_UNAVAILABLE / project_access=false；未准入项目数据，
没有 Kimi paid request。工具目录未暴露 codegraph/tool_search，本次按源代码调用链定位。

安装授权沿用用户先前明确授权。提交后执行正常 managed install 并核对结果；当前会话
权限可能阻止更新 ~/.agents，真实安装结果以后续记录为准。仓库无专用 capture Skill，
本记录保存 repair evidence。未修改 jianji、推送或发布；未宣称历史 502 已解决。
