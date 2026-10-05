# Kimi Unknown-Outcome Replay Repair — 2026-10-05

## Incident And Boundary

AI-VIDEO session `01a107ea-b425-7fe2-8764-606d9cbdecd7` 的 Kimi invocation
`7d68d310-8520-427e-b52b-854476d153bf`，以及本仓库只读调查 invocation
`17c25c00-dd42-47fb-8c41-a6562e4a3788`，均在第三个 wire request 已收到
HTTP 200 和超过 1 MiB 响应正文后，约 328.5 秒处发生
`RESPONSE_BODY/CONNECTION_ERROR`，终态为 `OUTCOME_UNKNOWN`。两次均无完整
worker report；partial 输出继续隔离，历史 receipt 不改写。请求的生成上限是
32,000 tokens、wall 3,600 秒、idle 1,800 秒、output 16 MiB，不是本地额度耗尽。
其他历史请求在约五分钟后也有成功例，因此不能把这两次归因于一个已证明的固定上游时限，
更不能声称本地代码能防止服务端或中间网络断连。

## Root Cause And Change

本地 broker 的 `RouterError('OUTCOME_UNKNOWN')` 与 generic exception 路径返回
502 后未撤销 project invocation。一次断连后，同一 runtime 可再次发起 wire request；
这是与 accepted Spec E2 的 no-automatic-replay 边界不符的本地缺口。源代码调用链为
`KimiUpstream.__call__` → `UpstreamFailure` → `Broker.Handler.do_POST`；安全异常分类、
HTTP 状态和已接收 byte 计数仍由原 owner 保存。

现在两条 `OUTCOME_UNKNOWN` 路径均撤销 invocation，再请求只返回
`CAPABILITY_REVOKED`，不发生第二次上游调用。成功响应、多次合法工具请求、
model/route 身份校验、secret 检查、预算、receipt 分类均未放宽；不重试、不尝试
从不完整 SSE 推断终态，也不修改用户选定的 `deep/max/32,000` policy。

## Verification And Delivery

- 修复前：contract 断连用例和 generic exception 撤销断言均为 RED；实测同一
  invocation 的第二次请求仍送入 fake upstream（两个 502、两个 wire calls）。
- 修复后：focused transport `83 passed`；Micromamba offline `1077 passed, 35 skipped`；
  Micromamba native/fake + containment `1099 passed, 13 skipped`。skip 不视为资格证明。
- 修改文件的 Ruff 检查、`git diff --check` 通过。全仓 Ruff 尚有八处旧错误，均在未修改的
  `tests/unit/test_gpt_astra_image_route.py`，未顺带改动。
- 实施 commit `67095fe7882704180b756b32f0c9d94e117b5bad` 已由官方 installer
  clean 安装，manifest `source_hash=1d5d468c851934b2935500efef71ff4c0cb8924e0f68c6237c5a15553e1edb70`；
  entry/Skill SHA 与 manifest 一致，installed `broker.py` 与 source bytes 一致，
  installed package 的 fake disconnect 验证为首次 502、再次 403、仅一次 wire call。
  安装后 `subagent doctor --backend kimi` 的本地 Docker/native 检查通过；这不是新的
  live Kimi 报告、真实长生成稳定性或用户任务验收。

## Risk Gate And Remaining Risk

Stable candidate 为 commit `67095fe`；适用 accepted Spec E2/E3/G2，无新 Plan。
`KIMI_REVIEW_NOT_REQUIRED`：用户未要求该 snapshot 的 Kimi review；变更仅收紧
unknown 后的准入，没有凭据、model、权限或项目状态放宽。原 failure path 的不变量有
RED→GREEN contract test、generic exception unit test、全套 offline/native fake 以及
installed-package fake 请求覆盖；未发现 project-native verification 后仍有重大语义缺口
而需要额外 Kimi adversarial review。此前只读 Kimi 调查是 `OUTCOME_UNKNOWN`，不计审查通过。

远端连接仍可能在生成中途断开，故没有承诺 Kimi 长请求必达终态。Parent 应在旧 receipt
和已消耗预算检查后，将调查拆成更小且有独立证据要求的 sealed 工作单元；这只能降低风险，
不能代替成功 receipt。连续两次同一有界单元运行失败时，按
`/home/reggie/.codex/SUBAGENTS.md` 的 native fallback 接手，而非盲目第四次调用。
