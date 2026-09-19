# Implementation Checkpoint

## Outcome

2026-09-19，完成可独立推进的M2–M5离线实现、M1固定runtime native-loopback probes、MM-01…MM-10 synthetic回归与薄CLI/Skill安装能力。**没有完成M1–M9全量验收**。M1a live credentials缺失、M1b namespace失败是两个真实blocker；M6、M7 live、M8、M9保持blocked/not implemented。没有更改AI-VIDEO、jizhang、旧MiniMax runner或Claude/global policy。

## Verification

当前 source tree 执行：

```sh
micromamba run -p /home/reggie/micromamba/envs/ai-video-p2 python -m pytest -q tests/unit tests/contract tests/regression tests/conformance --native-conformance
/home/reggie/.local/bin/ruff check src tests
git diff --check
```

结果：117 tests PASS；ruff PASS；diff whitespace检查PASS。Native conformance是显式3 tests，使用真实Claude2.1.277与本地fake upstream；默认suite不调用provider。这不包括live identity、OS containment、项目8次holdout或1M entitlement。

## Independent Review

Native `reviewer_max` 使用profile固定 `gpt-6-astra / max`，没有声称ultra。Read-only审查发现并经parent复现修复：durable observer secret泄漏、cancel/send窗口、SSE最终usage丢失、receipt同UUID foreign-path逃逸、evidence行范围、畸形manifest、instruction-seal竞态、late handler回写、Skill安装漂移、project-local JSON Skill资产和外部accepted/Harness refs投影遗漏。新增回归tests绑定真实failure modes。

最终review verdict：`accept with concerns`，限定实现中无剩余blocking issue。Reviewer独立运行同一117 tests并确认检查期间source/tests/Skill hashes未变化。Remaining concern是未进行真实凭据/containment/holdouts以及安装入口切换期间SIGKILL/断电恢复；正常可捕获I/O失败已有rollback测试。review不替代任何未通过的live/OS门槛。

## Installation

安装仅使用新owner：CLI `~/.local/bin/subagent`，parent Skill `~/.agents/skills/external-subagent`，versioned source/Skill snapshot `~/.local/share/agent-subagent-router/installations/<source-hash>/`，receipts `~/.local/state/agent-subagent-router/runs/`。受管CLI与Skill每次调用核对hash；未知入口不覆盖。安装metadata保存source commit、source hash、entry hash、Skill hash；rollback保留历史source与receipts。

实际安装完成，source commit 为 `c0ce5b57b748d06bc8f9536c8dd00f1284e607a4`，source/Skill hash 为 `2eb18524489b02105fe15dccd872b20cb7a2f9ef50383baf9dc48833db403041`，安装时 source/Skill clean。`subagent --version` 返回 `0.1.0`；installed `inspect → run(BLOCKED_CAPABILITY) → receipt` 的generic fixture链路通过，wire requests=0。固定snapshot内代码再次运行worker/deep native-loopback并读取receipt hashes通过。见 [installation.json](installation.json)、[installed-cli-check.json](installed-cli-check.json)、[installed-doctor.json](installed-doctor.json)。

已安装入口的两次M1 live命令均返回 `CREDENTIAL_REQUIRED`，process=null、wire_requests=0，并保留typed receipts；不是失败后盲重试Provider，也不消耗两个真实smoke预算。该阻塞是缺少本地provider-specific credential reference，不推断其他未检查位置或用户账号状态。

## Remaining Work

- M1：本地注入Kimi credential；在不弱化host安全策略的环境完成M1b adversarial qualification；核实deep entitlement。
- M6–M7：真实read-only role enforcement及parent独立test domain；freeze双项目rubrics后执行8次matched holdout并parent复核。
- M8：基于已qualified基础实现candidate writer、exact ownership/preimage、candidate/final gates和parent apply。
- M9：不同native runtime/provider的相同contract suite、明确有限预算与双项目live proof。

没有M7 usable result，因此cost per usable result为unknown，不能报零。没有用退出码、文档、fake身份或review verdict代替产品验收。

## Record Evaluation

本仓库无专用session capture skill；本checkpoint和hash绑定JSON是durable record owner。AI-VIDEO仅在既有baseline研究资料中作为holdout名称，无本轮项目或media effects，不调用该项目record skill、不创建项目记录。未修改Codex memories。
