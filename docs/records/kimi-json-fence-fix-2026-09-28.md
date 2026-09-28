# Scope

修复 session `01a0e6db-9261-7a41-b62c-0224e914c096` 的 invocation
`3c5ec80e-00df-46ea-ad99-6d02587d9e36`：终态报告内容为有效五字段 JSON，
但外层 `json` Markdown 围栏导致 strict parser 返回 PROTOCOL_ERROR。
该 invocation 正常退出、没有截断，并有四次可校验 Read；不是 timeout。

# Contract And Owner

唯一变更 owner 为 `protocol._report_json`，representation policy v1：只允许整个
terminal result 是一层完整、明确标注小写 `json` 的三反引号围栏，边界换行可为 LF/CRLF，
外部仅允许 JSON whitespace。移除这一层后继续调用原有 strict_json、validate_report
及 Read/hash/range/required-evidence 检查。没有 JSON extraction、语义修补或 retry。
其它语言/无标签围栏、额外解释、多个对象、嵌套围栏、重复 key、非有限数值和非法 JSON
仍失败。报告字符串内的普通反引号文本不修改。

遵守 accepted Spec E5 的无歧义 representation normalization contract；不改变 wire
五字段 schema、model/profile、permission、qualification、candidate/apply 或 acceptance。
保存的 stdout artifact hash、receipt router implementation hash 和本 commit 的 v1 policy
共同绑定原始输入及变换版本；新调用的 worker-report artifact 仍保存验证后的报告。
没有新增 durable state owner，不回写历史 invocation。

# Verification

- Regression tests 修复前 3 failed、23 passed；修复后 protocol/evidence/project/Gemini/
  receipts/projection/MiniMax suite 65 passed。命令：
  `micromamba run -n ai-video-p2 python -m pytest -q tests/unit/test_protocol.py tests/unit/test_evidence.py tests/unit/test_project_run.py tests/unit/test_gemini.py tests/unit/test_receipts.py tests/contract/test_projection.py tests/regression/test_minimax.py`。
- Installation/writer/candidate/Gemini-evidence/generation/output suites 66 passed：
  `micromamba run -n ai-video-p2 python -m pytest -q tests/unit/test_installation.py tests/unit/test_writer.py tests/unit/test_candidate_gates.py tests/unit/test_gemini_evidence.py tests/unit/test_generation_budget.py tests/unit/test_output_budget.py`。
- 实际 artifact replay：校验全部 artifact hash/size，从原始 Read events 重新计算并核对
  四项 observed_reads，再用 sealed source hashes 与 required evidence 解码，结果 PARSED。
  stdout SHA-256 `c65af3037fc4a87502cd2774a7b51adffb5a723f24bd05e3029a731f9296dda1`。
  历史 receipt SHA-256 `0384d43cf7fc61d7190fd1b484872444f27f76f12e40edbc83e2575a87ecfed1`
  未改变，仍为 PROTOCOL_ERROR / parent_acceptance NOT_EVALUATED。
- `git diff --check` 通过。未运行全套 socket/native/live tests，不声称 live qualification
  或业务 acceptance；既有 MiniMax contradiction regression 仍通过。

# Risk Gate And Delivery

Stable candidate 为本记录所在 commit；changed paths 为 protocol.py、test_protocol.py 与本记录。
Spec 为当前 accepted architecture contract E5/G2；durable implementation Plan 不适用。
G2 结果 KIMI_REVIEW_NOT_REQUIRED：用户要求修复，未明确要求该 candidate 的 Kimi review；
该局部无歧义变换不放宽 source evidence、schema、tool、route 或 acceptance predicates；
未识别 critical credential/authority/production-state consequence，也未识别重大后果、
剩余实质验证缺口、Kimi 独立增益同时成立的证据。负例测试与实际 artifact replay 覆盖边界。

Standing delegation preflight 按 external-subagent Skill 执行 doctor，当前结果
BLOCKED_CAPABILITY / SANDBOX_IMAGE_UNAVAILABLE / project_access=false，未获项目数据准入，
因此没有新增 Kimi Provider request，也不将该 preflight 计为独立审查通过。

安装授权仍有效，当前环境 `~/.agents` 为只读，managed installer 需在可写会话或普通终端
更新入口。本轮未切换当前安装；安装前仍使用 fc9e11c。源代码修复不证明语义结论正确，
不清除任何项目已有 review blocker；PARSED 仍由 Parent 单独裁决。
仓库无专用 capture Skill，本记录为 durable repair evidence。未 push/release。
