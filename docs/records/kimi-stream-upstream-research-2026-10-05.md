# Kimi Stream Upstream Research — 2026-10-05

## Scope And Local Surface

本记录仅汇总一手来源，不构成 live-provider 诊断。未发送认证请求、使用凭据、修改主机或网络设置。仓库事实于 2026-10-05 核对；故障耗时与 Mihomo 观察来自 Parent 提供的 incident packet，本轮未重新探测。

路由器在 `src/agent_subagent_router/backends/kimi.py:15` 固定使用 `https://api.kimi.ai/coding/`。`src/agent_subagent_router/transport/broker.py:52-128` 仅允许 `/v1/messages`，只连接 `api.kimi.ai`，将 `/coding` 与请求路径拼接后通过 `http.client.HTTPSConnection` 发送；它关闭自动重连、用 `read1()` 缓冲响应块并在结束时关闭连接。`src/agent_subagent_router/transport/identity.py:37-83` 解析 SSE，要求唯一的 message identity 与 `message_stop`，随后检查 secret 和 model identity。

## Endpoint And Service Findings

Kimi 官方 [Kimi Code API 文档](https://www.kimi.com/code/docs/)说明 Code API 同时兼容 OpenAI 与 Anthropic 协议。文档列出国内 Anthropic 地址 `https://api.kimi.com/coding/`、海外地址 `https://api.kimi.ai/coding/`，并以 `/coding/v1/messages` 为 Anthropic endpoint 示例。[Claude Code 接入文档](https://www.kimi.com/code/docs/en/third-party-tools/claude-code.html)本身配置 `api.kimi.ai/coding/`，并说明 `/status` 应显示该 Base URL。**置信度高：** 当前 `.ai` hostname 是官方文档列出的海外 Coding API 地址；`.com` 是国内对应地址，不能据此视为适用于所有账户或区域的通用故障切换地址。

Kimi [FAQ](https://www.kimi.ai/help/kimi-code/faq)区分 Coding 会员端点与另行计费的 Open Platform 端点。`api.kimi.ai` / `api.kimi.com` Coding 路由不能与 `api.moonshot.ai` / `api.moonshot.cn` Open Platform 路由混为一谈。查阅的官方文档没有公布流式请求时长 SLA、服务端 SSE 生命周期上限或公开 API 状态/事故页面。FAQ 所述 30 秒超时针对 VS Code extension 的连接体验，不是 Coding API 的生成流超时。**路由区分的置信度高；对所查页面是否涵盖所有状态信息的置信度低。**

Parent 提供的记录显示 `.ai` 经 Mihomo `PROXY HK03`、`.com` 经 `DIRECT`，未认证 TLS `HEAD` 耗时约为 5.38 秒和 0.15 秒。这些观察只反映特定网络路径；它们没有比较认证后的 `/coding/v1/messages` 请求，不能证明付费请求可靠性、代理是根因或 `.com` 更优。

## SSE Completion Semantics

Anthropic 官方 [streaming 规范](https://platform.claude.com/docs/en/build-with-claude/streaming)规定 `message_stop` 是 Messages stream 的最后一个事件，之前可以出现 `ping`。Kimi 将其 endpoint 标为 Anthropic-compatible，因此把该终止事件约束应用于 Kimi 路由，是基于协议兼容性的推断，不是 Kimi 专门作出的保证。**Anthropic 协议语义置信度高；对 Kimi 兼容端点的适用性置信度中高。**

单独的 HTTP EOF 不是应用层完成事件。若先收到 `message_stop`，随后 EOF 可视为正常关闭 body；若缺少该事件，响应就是不完整流，不能作为成功交付。路由器已在 `identity.py:61-68` 检查此条件，不以 HTTP 200 或收到的字节数替代。`message_stop` 只证明协议流结束；model identity、secret 检查、报告校验和 Parent acceptance 仍须通过。

## Long-Stream Failure Evidence

[MoonshotAI/kimi-code issue #1798](https://github.com/MoonshotAI/kimi-code/issues/1798)中，报告者描述响应头后已收到部分内容、随后流静默的情况。报告将其归因于 OpenAI-compatible client 在收到响应头后就结束 request timeout，并指出空 SSE keepalive 可能绕过较低层的 body timeout。这是官方仓库中的 issue 报告，不是 provider RCA；它针对 `api.moonshot.ai` / Kimi OpenAI-compatible 路径，不能证明本路由的 `api.kimi.ai/coding/v1/messages` 有同一故障。**作为故障模式类比的置信度中等；作为本次事故根因证据的置信度低。**

[PR #1799](https://github.com/MoonshotAI/kimi-code/pull/1799)提出在每次 stream iterator 读取外增加 180 秒静默期限；超时后中止 provider 请求，并在 `finally` 中关闭 iterator。其后续说明，最初的 cancel 路径实际上没有关闭真实 provider stream；修正方式是中止底层传输并关闭 iterator，且不要等待可能卡住的 `return()`。#1799 后来关闭并由 [PR #2446](https://github.com/MoonshotAI/kimi-code/pull/2446)取代；后者将思路应用到较新的代码路径。查阅页面不能证明任一改动已发布。该模式可把静默挂起变成有界失败，但 PR 中的 retryable error 和自动 step retry 与本路由 no-replay policy 冲突，不应照搬。

旧版 [MoonshotAI/kimi-cli 仓库](https://github.com/MoonshotAI/kimi-cli)已明确归档且不再维护；其 [issue #2582](https://github.com/MoonshotAI/kimi-cli/issues/2582)报告流中断后 CLI 无限等待。仓库也将旧 `kimi-sdk` package 列为归档。上述内容仅作历史故障现象参考，不是当前修复，也不能证明 Coding API 有同样问题。

Anthropic 官方 [Python SDK](https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python)和 [TypeScript SDK](https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/typescript)文档提供 SSE streaming、可配置 timeout，以及通过 `max_retries=0` / `maxRetries: 0` 关闭默认自动重试的选项。Python SDK 还暴露细分的 `read` timeout；文档建议长请求使用 streaming，并提到网络可能因连接空闲而断开。这些属于客户端控制，可限制等待并关闭流，但不能证明或修复上游断连。Kimi 的 Anthropic 兼容声明也不保证其服务完全符合 SDK 的每项行为。**SDK 配置选项的置信度高；用于 Kimi 兼容端点时的行为置信度中等。**

## Assessment And Safe Falsifiers

Parent 提供的记录包含两次 HTTP 200 后的 body 失败：约 328.5 秒、已收取超过 1 MiB；另有超过 338 秒仍成功的流。这些事实不能证明服务端存在固定的 328 秒上限。传输正在持续交付 body 时发生连接重置，与流停止产生新字节后的静默超时也不同；idle watchdog 能处理后者，不一定能处理前者。

保持当前按区域选择的 `.ai` endpoint 明确绑定。不要根据未认证 `HEAD` 耗时切换到 `.com`、绕过 Mihomo 或添加 endpoint fallback。后续若要区分假设，可在可行时用脱敏后的 upstream request/trace ID 对照 provider 日志；只有在单独授权后，才以区域匹配的 key 发起一条认证请求且不重试，比较路由行为。无需连接 Kimi 的本地 fake-upstream 测试可独立验证 parser 与 EOF 行为。

若后续获准改代码，应先确认当前 `HTTPSConnection` timeout 实际约束什么。可另设有界 read-idle guard，将静默分类为失败并中止/关闭 socket，保留已观测的 HTTP 状态、字节与耗时计数，撤销 invocation 并返回 `OUTCOME_UNKNOWN`；不得 replay、fallback、接受 partial SSE，或把 HTTP 200 当作成功。验证应覆盖延迟字节、body 中途重置、keepalive/ping、缺少 `message_stop` 的 EOF，以及收到 `message_stop` 后的 EOF。本研究本身不建议修改 source。

## Source List

- Kimi Code endpoint 与协议：[官方概览](https://www.kimi.com/code/docs/)；[Claude Code 接入文档](https://www.kimi.com/code/docs/en/third-party-tools/claude-code.html)；[Kimi Code FAQ](https://www.kimi.ai/help/kimi-code/faq)。
- SSE 事件契约：[Anthropic streaming 文档](https://platform.claude.com/docs/en/build-with-claude/streaming)。
- 官方仓库材料：[kimi-code #1798](https://github.com/MoonshotAI/kimi-code/issues/1798)、[#1799](https://github.com/MoonshotAI/kimi-code/pull/1799)、[后续 #2446](https://github.com/MoonshotAI/kimi-code/pull/2446)；已归档的 [kimi-cli](https://github.com/MoonshotAI/kimi-cli)及 [#2582](https://github.com/MoonshotAI/kimi-cli/issues/2582)。
- 官方 SDK 控制项：[Anthropic Python SDK 文档](https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python)；[TypeScript SDK 文档](https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/typescript)。

## Verification

已读取官方文档、本地 source、`kimi-code` #1798/#1799 与已归档 `kimi-cli` #2582。#2446 的取代关系与范围依据 #1799 中的明确交叉引用核实；直接读取 #2446 页面失败。本文件仅为文档记录；未运行代码测试或 live-provider 调用。
