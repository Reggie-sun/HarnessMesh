# Kimi Maximum Project Resources

## Status And Authorization

`SOURCE_FIXED / INSTALL_PENDING`。

用户在 receipt `f244c937-eb0d-4216-9324-da7840e57be1` 的 8192-token 截断后要求“全局都开最高”，并选择 C：新 Kimi project task 的 profile、生成、wall/idle、requests、output 和 context 均使用当前支持的最高值。此前已有受管安装更新授权。本轮只落实该明确、有限的 sizing policy；不创建 Spec/Plan，不改业务项目，不 push/release。

Canonical architecture Spec 保持 `docs/superpowers/specs/2026-09-23-harnessmesh-rare-review-design.md` / SHA-256 `a3c216c077608767e1ac7ac7d03869e8d90f49256469691e8206c71edbf3566c`。其 finite sealed budgets、explicit route、qualification、no fallback 与 Parent authority 不变；没有发现需要修订 Spec 的 defect。

## Owner And Behavior

`api.inspect_task` 在原 task 验证通过后、`resolver.resolve` 封存前应用 `kimi-maximum-v1`。Validator ceiling 由 `contracts.BUDGET_LIMITS` 与 Kimi 专有 generation/idle ceiling 独占；新 task 的有效 profile 为 `deep`（client `k3[1m]`、wire `k3`、effort `max`、configured context 1048576 tokens）。新 seal 中的 budgets 为 generation 32000、wall 3600 秒、idle 1800 秒、64 次 requests、16 MiB output、8 MiB context。它们是本地已支持 ceiling，不是无限预算或当前 upstream provider-wide maximum。

新 manifest 的 `transport.resource_policy` 绑定原请求 profile/budgets，CLI 展示 effective `route`/`budgets` 与 policy；原 task 文件不改写。有效低额度旧 task JSON 经新 inspect 得到明确的新最大额度 seal；unknown profile、非法/超界 budgets 仍失败，不被归一化“修好”。范围、refs、capabilities、权限和 acceptance 不变。旧 seal 仍可按原 profile 和较低额度执行，不在 `run_contract` 应用新策略；Gemini 和独立 image contract 不继承此 project policy。

Runtime generation env 接收封存的 32000；broker 的实际 cap、上游截断拒收/revoke、source drift 校验、timeout/cancel、无自动 retry 与 qualification/entitlement gates 未放宽。Pinned runtime 使用 adaptive thinking 的实际 wire observation 不由 `MAX_THINKING_TOKENS` 自述证明；仍只声明 requested max，不声称已证明实际 reasoning 强度或实际 1M consumption。

## Snapshot

Code baseline commit: `ea05c07`；并发文档 checkpoint `8b05ea4` 的其他任务内容保留。当前 source/Skill content-addressed installation hash：`30ab9cd4a72e67a4e2d17cd65a8d9eac1446ed6157a31493e6a625a4bb656323`。

| Owned source | SHA-256 |
| --- | --- |
| `src/agent_subagent_router/api.py` | `edb456ed59895e54b2a4f9736400dbd717bc9ed19d751b7c9887009bc927ee13` |
| `src/agent_subagent_router/cli.py` | `1ea97897f844cf5b6080f592e2e7cca8d62f9de473d2655c5dc542ad85d995b5` |
| `src/agent_subagent_router/contracts.py` | `0833caaa7a62593f24a510bb3a32c351c37a1cf9e7d5daf7e46b78a487edfc13` |
| `skills/external-subagent/SKILL.md` | `7f3cb1df74d8fd45f45424ac8345bf6814e77b8dfed6203975af34bd9237e7ee` |

Owned tests：new `test_kimi_maximum_resources.py`；generation/output/API tests 更新当前新-seal 预期；project/writer conformance 使用原 worker/4096 fixture，以保留历史 frozen contract 的实际执行检查，而不是取消旧保护。README/Skill 同步 effective route 的调用方法；未修改独立 image source、Spec 或其他用户 dirty artifact。

## Verification

- TDD RED：6 个资源/profile cases 与 CLI exposure case 因原代码保持低预算而失败；初次共 7 failed / 3 passed。GREEN 后同批行为已通过。
- Focused executable suite：`PYTHONPATH=src /home/reggie/micromamba/envs/ai-video-p2/bin/python -m pytest -q tests/unit/test_kimi_maximum_resources.py tests/unit/test_generation_budget.py tests/unit/test_output_budget.py tests/unit/test_api.py tests/unit/test_contracts.py tests/unit/test_protocol.py tests/unit/test_supervisor.py tests/unit/test_claude_timeouts.py tests/unit/test_project_run.py tests/unit/test_route_qualification.py tests/unit/test_installation.py`：**131 passed**。
- 完整 offline suite：**376 passed / 25 skipped / 42 failed**；JUnit `/tmp/harnessmesh-kimi-maximum-offline-final.xml` 的全部 42 failures 均为 `PermissionError: [Errno 1] Operation not permitted`（socket 创建，包括 fake broker/Docker socket fixture），不声称完整 suite 通过，也未修改 tests/runtime 来绕过沙箱。
- `/home/reggie/.local/bin/ruff check src tests scripts` 和 `git diff --check`：PASS。
- `subagent doctor --backend kimi` 返回 `BLOCKED_CAPABILITY` / `SANDBOX_IMAGE_UNAVAILABLE`。Docker exact image inspect 的实际错误为连接 `/var/run/docker.sock` 时 permission denied。受管 read-only mapping task `/tmp/harnessmesh-kimi-maximum-mapping.task.json` 的 canonical inspect 同样 preflight refusal；无 manifest、无 Provider request、无 Kimi report，不计作独立审查通过。
- `superpowers:writing-skills` 的 reference baseline 查得旧说明会选择 worker/4096 并保留低额度。更新后的独立 reference application check 正确选择 deep/32000、归一化低预算、使用有效 deep qualification、保留旧 worker/8192 seal，并区分 64 wire requests 与三轮 review。其发现的“缺省 generation 输入是否允许”说明缺口已补充并复查：新 task 可省略、旧 seal 缺项仍拒绝。它是调用说明测试，不是额外 Codex implementation reviewer 或 Kimi replacement。

## Review Risk Gate And Parent Adjudication

`KIMI_REVIEW_NOT_REQUIRED`，适用 canonical Spec G2。用户要求修改最高资源策略，没有要求对本 snapshot 发起 Kimi implementation review。没有新增 credential exposure、权限/跨项目范围失效或不可恢复 production/durable-state failure path；全部上调仍在原 validator 的有限 ceiling 内，并在新 seal 中明示。Profile 变更需有效 deep qualification，无法取得时仍拒绝，不能退回 worker。

具体 verification gap 是本会话 socket/Docker 不可用，故未获得 native/fake E2E 或新的 live 性能证据；这是环境门的缺口，不通过模型意见闭合。新-seal sizing、CLI 透明性、原范围保留、非法输入、有限输入边界、runtime env 和旧-seal route/额度已获 focused executable evidence；未发现同时满足 G2“重大失败后果 + 实质语义缺口 + Kimi 可补独立增益”的具体风险。因此不添加 expensive final review，也不伪造 required gate 完成。Standing Kimi 调查尝试仍因真实 preflight blocker 未能运行，与 final-review Risk Gate 分别记录。

Parent 已检查 owned diff，无新的 confirmed blocking finding；安装和 native/live 边界不被描述为已通过。

## Historical Review Boundary

Jianji 的既有 8192-token seal/receipt 不改写。`f244c937-eb0d-4216-9324-da7840e57be1` 仍是 `UPSTREAM_GENERATION_LIMIT`，没有有效 terminal report；该项目获准的额外付费审查仍是 **1/3 consumed，remaining 2**。`request_limit=64` 只属于一个新 invocation 的 wire budget，不扩大三轮 governance 或该项目的额外 attempt 授权。本轮没有重跑 Jianji review，没有新付费 Provider request，也没有用 tests PASS 代替尚未完成的项目 required review。

## Installation

待 source checkpoint 后通过 canonical installer 更新；原 content-addressed package/receipts 保留，安装结果在此节追加。安装失败必须报告真实状态，不绕过 launcher/Skill hash guard 或 OS containment。
