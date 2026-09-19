# Agent Subagent Router

## Status

按用户最新要求，本次交付聚焦 **Claude Code / Kimi**；Gemini暂缓，已有partial成果与blocker保留记录。

Kimi 的 M1–M7 read-only 路线已完成本机 live qualification；M8 单文件 candidate → parent test → apply → readback 已实际通过。M9 的 Gemini adapter、独立 native runtime、隔离与 fake upstream 已实现；现有 Google Code Assist 凭据返回 `UNSUPPORTED_CLIENT`，两项目 live 验收尚未通过。不能宣称 M1–M9 全部完成或跨 backend live portability 已验证。

当前状态见 [implementation-status.md](docs/implementation-status.md)，验收证据见 [final-qualification.md](docs/records/final-qualification.md)，架构图见 [baseline spec](docs/baseline/specs/global-external-subagent-infrastructure.md)。本 repo 是唯一 global source owner；业务 Harness 和 parent acceptance 保留原 owner。

## Invocation

```sh
subagent --version
subagent doctor
subagent doctor --backend gemini
subagent inspect --cwd /absolute/project --task /private/task.json
subagent run --contract /private/snapshot/manifest.json --backend kimi --profile worker \
  --live --credential-ref ~/.config/agent-subagent-router/kimi-credential.json \
  --qualification <canonical-route-qualification-id>
subagent receipt <invocation-id>
```

`doctor` 运行 OS/native adversarial probes，仅使用 fake upstream；`CONTAINMENT_QUALIFIED` 不代表账号、live identity 或质量合格。`inspect` 封存 source/route/runtime/image，不联网或执行项目 scripts。`run` 不能覆盖 sealed route/权限/预算，每个真实 contract 最多提交一次；`PARSED` 不等于 KEEP。

Task JSON 包含 parent/task identity、cwd、role、goal、read_paths、write_paths、permissions、selected_refs、active_documents、harness_refs、constitution_refs、skills、skill_roots、expected_evidence、backend/profile 和 budgets。无 Git 时给 explicit_root；没有 active docs 填 `not_applicable`。选中 spec/plan ref 为 `{path, sha256, accepted: true}`。

Kimi profiles：`worker` (`k3-256k/high/adaptive`) 与 `deep` (`k3/max/adaptive`)。Key 只从 repo 外 owner-only provider-specific file 读取；本机 CC Switch key 已私密导入，原配置不改。`qualify-route` 将 canonical smoke 绑定当前 credential fingerprint；deep 另需 entitlement evidence。禁止删除 consumed/budget files 来重试。

## Scoped Writer

implementer 只允许一个已跟踪、干净的 owned file，权限 `read,candidate-write`。运行时增加 `--readonly-qualification <canonical-M7-id>`。worker 只读 immutable baseline 并编辑 private candidate，不挂载可写 host project，无 tests/shell/nested delegation/commit/KEEP 权限。

```sh
subagent candidate-test --invocation <candidate-id> --argv-json /private/exact-test-argv.json
subagent candidate-apply --invocation <candidate-id> --test <canonical-test-id>
```

测试 argv 为 JSON 数组，例如 `["/usr/local/bin/python3","/work/tests/check.py"]`；测试域无 broker、key 或网络。Apply 绑定 candidate/test hashes，检查 source preimage，使用 Linux `RENAME_EXCHANGE`，保留 displaced inode 和 durable recovery record，并核验实际 bytes。竞争时保留双方状态并报告 conflict/unknown，无自动 rollback。Parent 还必须执行应用后的项目原生 gates。多文件、新建、删除、rename、mode changes 不受支持。

## Gemini Boundary

独立 Gemini CLI `0.60.0` 使用 native `GEMINI.md` projection，只开放 `read_file,glob,list_directory`。selected Skills 尚未取得 native activation 证明，明确拒绝。固定 `gemini-3.5-flash`，无 fallback。Worker 只有一次性 capability；parent 读取既有 private OAuth file，经固定 Google token/preflight endpoints，再通过 Code Assist broker 调用模型。

Reference 为 `{"provider":"gemini","file":"/absolute/private/oauth_creds.json"}`；Gemini run 不要求 Kimi qualification 参数。不登录、onboarding、创建 Cloud project 或自动启用计费。当前账号被拒绝，零 generation requests。现有 transport 仅支持 OAuth；API key 不能直接替代，需另行实现和验收对应 transport。

## Verification

```sh
micromamba run -p /home/reggie/micromamba/envs/ai-video-p2 python -m pytest -q
micromamba run -p /home/reggie/micromamba/envs/ai-video-p2 python -m pytest -q \
  --native-conformance --containment-conformance
/home/reggie/.local/bin/ruff check src tests scripts
```

默认 tests 无真实 Provider；native tests 也只连本地 fake。完整 conformance 需 pinned images，并设置 `ROUTER_SANDBOX_IMAGE`、`ROUTER_SANDBOX_RUNTIME_SHA256`、`ROUTER_GEMINI_SANDBOX_CONFIG`、`ROUTER_GEMINI_RUNTIME_CONFIG`；skip 不算通过。MM-01…MM-10 synthetic regression 与无法关联原 terminal 的 historical evidence 分开记录。

## Installation And Rollback

```sh
PYTHONPATH=src micromamba run -p /home/reggie/micromamba/envs/ai-video-p2 python -m agent_subagent_router.installation \
  --source /home/reggie/vscode_folder/agent-subagent-router \
  --python /home/reggie/micromamba/envs/ai-video-p2/bin/python
```

仅管理 `~/.local/bin/subagent`、`~/.agents/skills/external-subagent` 与工具 versioned package/manifest；启动时核验 source/Skill hashes。Unmanaged/drift entry 不覆盖。`installation.rollback(Path.home())` 只删除 hash 匹配的入口及 ownership record，保留 source/packages/credentials/receipts。无 remote/push/release/worktree，旧 runner/global config 保留。

## Remaining Risks

Docker daemon 与 parent 是受信边界；parent SIGKILL/daemon 故障的 orphan recovery 未完整验收。Deep 配置与 entitlement 已验证，实际 1M consumption 为 NOT_EVALUATED。真实 Provider billing cost 未获取；小样本 holdout 不构成 provider-wide 性能承诺。
