# Local State Inventory

Date: 2026-09-19 (Asia/Hong_Kong)
Status: inspected; no router installation or provider invocation.

## Execution Identity

当前 session 的本地 `turn_context` 为 `model=gpt-6-astra`, `effort=ultra`；两组 native research agents 显式使用同一 model/effort。用户写的 `GPT-5.6 Astra` 不是当前 runtime 暴露的 dispatch identifier。`~/.codex/config.toml` 的默认 effort 是 `medium`，不能代替当前 session 的 `ultra` evidence。未修改模型配置。

## Installed Runtime

| Runtime/tool | Observed state | Evidence |
| --- | --- | --- |
| Codex | `codex-cli 0.154.0` | `/home/reggie/.local/bin/codex --version` |
| Claude Code | `2.1.77` | NVM Node `v22.21.0` 下 `@anthropic-ai/claude-code/cli.js --version` |
| Grok / Gemini / OpenCode / Kimi CLI | PATH 中未找到 | `shutil.which` |
| claude-code-router / AGPair / CodeRouter | PATH 中未找到 | `ccr`, `agpair`, `coderouter` |
| Micromamba | `2.5.0` | `micromamba --version` |
| bubblewrap | `0.9.0`，不可据此声称 sandbox 可用 | 下述 namespace probe 失败 |

`claude --help` 实际提供 `-p`, `--output-format stream-json`, `--include-partial-messages`, `--effort max`, `--tools`, `--permission-mode dontAsk`, `--setting-sources`, `--settings`, `--strict-mcp-config`, `--no-session-persistence`, `--disable-slash-commands`。也提供 `--fallback-model` 与 bypass flags；新 adapter 禁止启用后二者。当前官方文档涉及更晚版本，必须按已安装版本做 conformance，不能把最新文档当作 2.1.77 的实际行为。

## Existing Global Owners

| Path | Current role | Proposed treatment |
| --- | --- | --- |
| `~/.codex/AGENTS.md` / `SUBAGENTS.md` | global authority / native delegation policy | 保留；安装时只加经接受的最小 router pointer |
| `/home/reggie/AGENTS.md` | home workspace rules | 保留 |
| `~/.agents/{explorer,reviewer,writer,debugger}.md` | 旧 external runner definitions | 不作为新 router 的隐式 fallback |
| `~/.codex/skills/sub-agents` | symlink 到 Git-backed runner | 不原地重写 |
| `~/.codex/skill-repos/Reggie-skill/sub-agents` | 当前 MiniMax runner source | reference / regression source |
| `~/.config/sub-agents/credentials.env` | 旧 runner credential store | 仅看到 `MINIMAX_API_KEY` 声明；mode `0600`；不迁移 secret |
| `~/.claude/settings.json` | 用户现有 Claude 全局配置 | 不覆盖 |
| `~/.claude.json` | runtime 用户状态、MCP 配置 | 不复制到账户隔离目录 |

旧 runner repo 已有其他工作：`capture-minimax-session/scripts/capture_session.py`、`scripts/session_signals.py`、`tests/test_capture_session.py` modified。本任务没有修改它们。

## Provider And Credential Presence

Claude 全局 `env.ANTHROPIC_BASE_URL` 的 host 是 `api.minimaxi.com`；main/Opus/Sonnet/Haiku alias 为 `MiniMax-M3`；`ANTHROPIC_AUTH_TOKEN` present。顶层 `model=opus[1m]`，另有 permissions/plugins。这是多层 precedence 风险，不是 Kimi 配置。

已检查的 process environment、Claude settings、旧 runner credential store 中未发现 Kimi credential 声明；`~/.kimi`、`~/.config/kimi`、`~/.config/kimi-code` 不存在。**这只说明这些已知位置未配置，不说明用户没有购买、没有 key 或其他 credential store 一定为空。** 未读取 shell history，未搜索或导出 keyring secrets。

仅输出 credential presence、变量名、文件权限和公开 endpoint host；未打印任何 secret。Shell startup 检查仅记录变量名：`.bashrc` 有 Claude 非必要流量开关及 Codex 相关声明，未在所查 startup files 发现 Kimi/Moonshot 声明。

Kimi 若需初始化，用户应在 [Kimi Code Console](https://www.kimi.com/code/console) 创建 API Key，并在本地完成 secret store 注入；不得把 key 发到对话。具体安装命令在 accepted implementation 的 credential supplier 确定后提供，不能把尚未实现的 `login` 命令当成现有功能。官方 [Claude integration](https://www.kimi.com/code/docs/en/third-party-tools/claude-code.html) 提供配置流程；不执行其会清理现有全局 settings 的脚本。

## Skills And MCP

检查范围是三个 global skill roots 的直接子目录中存在 `SKILL.md` 的条目，不包含所有 plugin cache / nested bundles：

| Root | Skill directories | Symlink directories |
| --- | ---: | ---: |
| `~/.codex/skills` | 128 | 56 |
| `~/.agents/skills` | 68 | 0 |
| `~/.claude/skills` | 0 | 0 |

31 个重复 basename 中，1 个指向同一 realpath，30 个内容 hash 不同，例如 `team-review`, `brainstorm`, `workflow-plan`, `humanizer`。这不证明哪个版本错误，也不授权批量清理；它要求新 resolver 以 source path、hash、scope 和显式选择消歧。

Codex config 声明 MCP：`filesystem`, `cloudflare-api`, `node_repl`, `blender`。Claude 用户状态声明 `chrome-devtools`, `persistent-terminal`。本会话 callable tools 与本地配置并不完全相同，必须区分“configured”和“available”。当前 callable tool registry 没有 `codegraph` 或 `tool_search`；因此本轮依赖精确源码、symbol 搜索与离线 probes，不能声称完成 codegraph indexing。

## Sandbox Capability

实测命令：

```sh
bwrap --unshare-user --unshare-pid --ro-bind / / -- /usr/bin/true
```

退出 `1`，错误 `bwrap: setting up uid map: Permission denied`。这不是完整 sandbox 安全测试，只是该 namespace 路径在当前执行环境不可用的证据。不得为通过测试关闭主机安全策略。M1a 可在受信 CLI、空 cwd、隔离 config、无项目文档/工具/hooks/MCP 的条件下做 route-only probe；其 containment 仍是 `NOT_EVALUATED`。M1b 必须验证可执行的 OS containment；失败则项目源码和工具准入 `BLOCKED_CAPABILITY`，不降级为 prompt-only permissions。

## Holdout Candidates

### AI-VIDEO

Root `/home/reggie/vscode_folder/AI-VIDEO`；observed HEAD `6d63051171ddfaa12af079cebe7ad0b2f2f7a7fe`，working tree 有大量 staged/unstaged/untracked 现有工作。本轮不修改该项目。以 selected file bytes manifest 定义 holdout 输入，不能只写 HEAD 伪装成 clean tree。

Canonical pointers：`AGENTS.md`, `docs/agent-primary-contract-matrix.md`, `.agent/harness/policy.yaml`, `scripts/agent_harness.py`, runtime baseline、active parent-selected spec/plan。`CLAUDE.md` 也存在，不能假定与 AGENTS 完全相同。

按 `retrieve-ai-video-memory` 的 experience route，在 Micromamba `ai-video-p2` 尝试只读查询，失败于 `ModuleNotFoundError: langchain_core`；未安装 dependency、未重建 index、未改用网络 retrieval。改用当前源码及已有 sanitized diagnostics。

### Generic Project

选择 `/home/reggie/vscode_folder/jizhang`，普通 TypeScript/Fastify/React 应用，observed HEAD `144f71985adc5490f37d8367ea6b33a4c464b9c6`。有 `AGENTS.md` / `CLAUDE.md`、domain rules、fake-adapter tests；无需 AI-VIDEO Harness。

该树同样有大量现有 untracked files 和 credential-bearing `.env` backup 文件名。只选 `server/src/domain/rules.ts`、相关 tests 与 constitution 等源文件；排除 `.env*`、`server/data`、上传、真实财务数据。读取源码不授权调用 Actual Budget 或真实 VLM。

Project-native checks 按当前 `AGENTS.md` 为 `npm --workspace server test` 和 `npm run lint`；本轮尚未运行，M7 holdout 由 parent 在 accepted scope 中运行。AGENTS 中“优于任何单次对话偏好”的文字不能覆盖平台和用户的更高 authority，应明确记录该边界。

## Executed Verification

旧 runner baseline：

```sh
cd /home/reggie/.codex/skill-repos/Reggie-skill
micromamba run -p /home/reggie/micromamba/envs/ai-video-p2 python -B -m unittest discover -s sub-agents/tests -p test_dialogue.py
```

结果 `Ran 28 tests ... OK`。这是旧 dialogue parser 的离线证据，不是新 router tests，不是 Kimi smoke。

## Proposed Global Placement

- Source: `/home/reggie/vscode_folder/agent-subagent-router`，independent local repo；创建与安装在 research/spec/plan acceptance 后执行。
- Config: `~/.config/agent-subagent-router/`，非 secret backend profiles 与 credential references。
- Installed artifacts: `~/.local/share/agent-subagent-router/`，pinned runtime/projection packages。
- Private runs: `~/.local/state/agent-subagent-router/runs/<invocation_id>/`，directory `0700`，artifacts `0600`。
- Parent Skill: `~/.agents/skills/external-subagent/` 一个 canonical source；其他 roots 仅在实际 discovery 需要时建立受管 projection，不复制第二份可编辑内容。
- CLI: `~/.local/bin/subagent`，薄入口；不使用 existing runner 的默认 backend。
- 本轮待评审文档暂存在 `/home/reggie/docs/agent-subagent-router/`，未建立远程 repo，未安装 entrypoint。

## Record Boundary

本轮是 global infrastructure research，AI-VIDEO 仅作为历史 corpus 的只读来源。已评估 `record-ai-video-session`：不创建 AI-VIDEO 项目记录、不触发 learning adoption；全局 durable findings 由本评审包承载。未更新 Codex memories。
