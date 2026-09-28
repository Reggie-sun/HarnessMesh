# Scope

针对 session `01a0e346-39aa-7260-98c2-fd50751bc40e` 的 R2 invocation
`ec6040c1-a253-4dd1-9fe1-108680cce01a`，修复 Claude native evidence parser
误处理权限通知，以及 tool path 与 citation path 提示混淆。不修改 jianji，不重写旧 receipt。

# Root Cause

R2 已有终态 JSON，但六次宿主机路径 Read 被拒绝。native `system/permission_denied`
事件的 `message` 是字符串；`observed_reads` 对所有事件调用 `.get('content')`，
触发 AttributeError，随后被执行层归类为 PROTOCOL_ERROR。原始日志离线复现了该栈。

Single owner 为 `evidence.observed_reads`：只从 assistant/user 消息提取 Read evidence，
非会话通知不建立证据。nested event 拒绝、exact bytes/ranges、成功 Read 关联校验均保持。
`project_claude.project_prompt` 提供明确的 `/work/...` read_targets，宿主机 source_path
仅供报告引用，不用于工具读取；不扩大 mount 或 permission，不重试、不改变模型和预算。

# Verification

- 新增两项 regression tests，修复前均失败；修复后相关 evidence/protocol/project/projection
  suite：26 passed。命令：`micromamba run -n ai-video-p2 python -m pytest -q tests/unit/test_evidence.py tests/unit/test_protocol.py tests/unit/test_project_run.py tests/contract/test_projection.py`。
- 全套同环境执行：230 passed、40 failed、20 skipped；当前沙箱禁止 socket 操作，
  transport/native verification 不可完成，不声称全套通过。
- R2 原始 artifact 重放已越过权限通知；后续 exact-byte 校验拒绝含 `[REDACTED]`
  的源码片段。持久 stdout 已脱敏，不能用它重建未脱敏成功证据，更不能补签 PARSED。
- `git diff --check` 通过。未调用真实 Provider，没有第四轮 review。

# Risk Gate And Delivery

本次 bounded parser/prompt 修复为 KIMI_REVIEW_NOT_REQUIRED：用户未要求新增 review；
无新增权限、credential、writer 或 production side effect；拒绝事件仍不提供证据，
exact-source acceptance 检查保留，局部反例有可执行覆盖，未识别重大后果且剩余实质语义缺口
与 Kimi 独立增益同时成立的证据。stable candidate 由本记录所在 commit 绑定。
这是耗尽预算后的 Parent targeted repair，不以新任务名重置三轮预算，也不额外启动 delegation。

未部署：managed installer 会更新 `~/.agents/skills/external-subagent`，当前环境该目录为
只读，不尝试绕过或部分切换安装。须在可写且能执行 socket/native checks 的环境完成验证
与正常 managed install。源码修复不证明 Kimi 不再超时；新 prompt 的实际模型遵循尚未 live 验证。
jianji 的 REVIEW_ESCALATION_REQUIRED 不变；未 push/release。
