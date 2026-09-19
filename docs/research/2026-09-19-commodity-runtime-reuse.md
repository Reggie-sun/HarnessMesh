# Commodity Runtime Reuse

Date: 2026-09-19. Status: evidence for architecture exploration; no package adoption or implementation authorization.

## Finding

不能因为 agent framework 的 executor 不符合 HarnessMesh policy，就断言通用进程、取消或 HTTP transport 必须自研。更低层的 **AnyIO、HTTPX 和 ACP SDK** 已有可独立调用的接口。它们不提供项目 acceptance 或可信 provider identity，但这恰好允许 HarnessMesh 把机制复用与 authority policy 分开。

本报告由 parent 补充源码审计；源码 clone 到临时目录，没有安装依赖或修改 runtime。模块建议均为待设计批准的 research candidates。

## Maturity Snapshot

数据来源：GitHub REST repository metadata、release、contributors、commits 和 issue search，查询日期 2026-09-19。30d 起点 `2026-08-20`，90d 起点 `2026-06-21`。Issue/PR activity 为窗口内 **updated** 的对象数，包含旧对象的新活动；不是 opened 数。Commit 数为 default-branch API `since` 返回数，各项不足100，无分页截断。Contributors 标 `>=100` 的仅取首100，未伪造总数。

| Project / fixed HEAD | License | Stars / forks / contributors | Latest release | Latest HEAD commit | Commits 30d / 90d | Issues updated 30d / 90d | PRs updated 30d / 90d |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [encode/httpx](https://github.com/encode/httpx/tree/b5addb64f0161ff6bfe94c124ef76f6a1fba5254) | BSD-3-Clause | 15,502 / 1,592 / >=100 | 0.28.1, 2024-12-06 | 2026-02-23 | 0 / 0 | 3 / 3 | 5 / 8 |
| [agronholm/anyio](https://github.com/agronholm/anyio/tree/9e2b5924e54ce5fa6aacc0640846c1a360a45178) | MIT | 2,544 / 268 / >=100 | 4.15.1, 2026-09-05 | 2026-09-15 | 28 / 94 | 15 / 43 | 52 / 149 |
| [agentclientprotocol/python-sdk](https://github.com/agentclientprotocol/python-sdk/tree/d4b6f51cebe6b98226840d6adfe755b0757908ef) | Apache-2.0 | 324 / 40 / 22 | 0.12.1, 2026-08-16 | 2026-09-18 UTC | 11 / 30 | 2 / 8 | 11 / 29 |

HTTPX 的成熟 API 不能掩盖 release/commit 较慢；其 transitive `httpcore`、AnyIO、CA bundle 等仍需独立固定和升级审查。AnyIO 有持续 regression maintenance；ACP SDK 较年轻、protocol 仍演进。公开维护活动不是 release-to-release compatibility 或 native-runtime qualification。

## Reuse Decision Matrix

| Capability / needed behavior | Exact reusable module | Tests and known issues | Required adaptation | Mode / decision / reason |
| --- | --- | --- | --- | --- |
| Shell-free subprocess launch、stdout/stderr streams、async cancellation primitive | AnyIO [`open_process`](https://github.com/agronholm/anyio/blob/9e2b5924e54ce5fa6aacc0640846c1a360a45178/src/anyio/_core/_subprocesses.py#L122-L196), [`Process.aclose`](https://github.com/agronholm/anyio/blob/9e2b5924e54ce5fa6aacc0640846c1a360a45178/src/anyio/_backends/_asyncio.py#L1191-L1235), task groups/cancel scopes; MIT | [Subprocess regressions](https://github.com/agronholm/anyio/blob/9e2b5924e54ce5fa6aacc0640846c1a360a45178/tests/test_subprocesses.py#L243-L279) and [full-pipe/grandchild cases](https://github.com/agronholm/anyio/blob/9e2b5924e54ce5fa6aacc0640846c1a360a45178/tests/test_subprocesses.py#L443-L495). Historical issues #669 and #1166 below. | Pass argv sequence, explicit replacing env, cwd, `start_new_session=True`, empty `pass_fds`. Wrapper enforces aggregate output cap, wall/idle definitions, broker revocation, process-group/container cleanup and typed facts. Avoid unbounded-buffer `run_process` convenience API. | **WRAP — preferred mechanism candidate**. Does not introduce another orchestrator. Missing HM-specific budget/group policy is a wrapper requirement, not proof that subprocess implementation must be rewritten. |
| Fixed-endpoint HTTPS、bounded streaming reads、connection lifecycle、timeouts without inherited proxy or retries | HTTPX [`AsyncHTTPTransport`](https://github.com/encode/httpx/blob/b5addb64f0161ff6bfe94c124ef76f6a1fba5254/httpx/_transports/default.py#L279-L335), [`AsyncClient`](https://github.com/encode/httpx/blob/b5addb64f0161ff6bfe94c124ef76f6a1fba5254/httpx/_client.py#L1307-L1451); BSD-3-Clause | Existing transport/client/timeout suites; not run here. [Documented transport retry behavior](https://www.python-httpx.org/advanced/transports/) and [explicit environment control](https://www.python-httpx.org/api/). | Set `trust_env=False` on client and transport, `retries=0`, `follow_redirects=False`, fixed URL/SSLContext, bounded streaming consumer and external monotonic deadline. Do not accept upstream cookies/redirects as route authority or log credentials/bodies. Bound resource use for all chunks, not just Content-Length. | **WRAP — preferred HTTP mechanism candidate**. Existing stdlib transport remains current truth; replacement needs evidence, but HTTP framing/pooling/TLS need not be handwritten. Raw upstream identity extraction remains HM policy before any compatibility rewrite. |
| ACP framing、capability negotiation、typed session notifications and permission callbacks | ACP [`ClientSideConnection`](https://github.com/agentclientprotocol/python-sdk/blob/d4b6f51cebe6b98226840d6adfe755b0757908ef/src/acp/client/connection.py), [`Connection`](https://github.com/agentclientprotocol/python-sdk/blob/d4b6f51cebe6b98226840d6adfe755b0757908ef/src/acp/connection.py), schema; Apache-2.0 | [Connection recovery tests](https://github.com/agentclientprotocol/python-sdk/blob/d4b6f51cebe6b98226840d6adfe755b0757908ef/tests/test_connection_recovery.py), issue #85 below. No native ACP runtime tested here. | Bind SDK to parent-owned streams/process lifetime; deny permission escalation and terminals/filesystem callbacks not granted. Record negotiated protocol/capabilities as runtime facts. ACP model listing/session model is runtime-reported, not provider proof. | **WRAP — conditional per-runtime transport**. Reuse official protocol implementation when that runtime's ACP path meets native semantics; no compulsory ACP conversion of every CLI. |
| Combined ACP spawn helper | ACP [`spawn_stdio_transport`](https://github.com/agentclientprotocol/python-sdk/blob/d4b6f51cebe6b98226840d6adfe755b0757908ef/src/acp/transports.py#L47-L118), [`spawn_agent_process`](https://github.com/agentclientprotocol/python-sdk/blob/d4b6f51cebe6b98226840d6adfe755b0757908ef/src/acp/stdio.py#L162-L183); Apache-2.0 | Stdio tests exist; native group cancellation/identity not established | Default helper merges selected host env even with provided env; exposes no `start_new_session` parameter and waits/terminates direct child. Parent-owned process supervisor can supply streams to connection API instead. | **REFERENCE_ONLY for this helper**, while the protocol remains WRAP. Rejecting one convenience helper does not reject the SDK. |

These modes cover mechanisms only. They do not select CUSTOM for the whole supervisor, model router, projection compiler or receipt store. Authority-specific code and any unavoidable platform shim require a separate, exact burden-of-proof in the proposed design.

## Negative Evidence And Compatibility

- **AnyIO #669 — historical timeout/cancellation cleanup defect.** Reported on 4.2.0; closed through a fix. Current source includes cancellation/orphan regressions. [Issue](https://github.com/agronholm/anyio/issues/669). This does not prove all grandchildren are killed; `.kill()` still targets the direct process, so container/group cleanup remains required.
- **AnyIO #1166 — historical full-pipe shutdown deadlock.** Current source has a dedicated regression and version history identifies the fix. [Issue](https://github.com/agronholm/anyio/issues/1166), [version history](https://github.com/agronholm/anyio/blob/9e2b5924e54ce5fa6aacc0640846c1a360a45178/docs/versionhistory.rst). Closed issue status alone was not used as conformance proof.
- **HTTPX breaking changes.** 0.28 removed deprecated `proxies`/`app` arguments and changed JSON serialization/URL handling. A request SHA must bind actual transmitted bytes, not an assumed encoding from a Python object. [0.28 release](https://github.com/encode/httpx/releases/tag/0.28.0), [changelog](https://github.com/encode/httpx/blob/b5addb64f0161ff6bfe94c124ef76f6a1fba5254/CHANGELOG.md).
- **ACP #85 — EOF could leave pending requests hung.** Reported against 0.8.1, closed by #86. Current connection implementation and recovery tests were inspected; no full SDK suite or CLI integration was run. An outer bounded deadline remains necessary even when protocol close is expected. [Issue](https://github.com/agentclientprotocol/python-sdk/issues/85).
- **Provider scope.** These libraries do not claim Kimi/GLM/Grok/Gemini runtime compatibility; provider-specific failure reports belong to the gateway/runtime matrices. Transport-library correctness cannot certify a model route, tool schema, MCP integration or structured semantic report.

## Executed Research Probe

Current environment already had AnyIO 4.14.2 and HTTPX 0.28.1; neither was upgraded. The probe used `PYTHONPATH` pointing to the inspected AnyIO clone and asserted `anyio.__file__` was under that clone, so installed-version metadata was not substituted for tested bytes.

Importing the full upstream subprocess test module initially failed on missing `pytest_mock`; the complete suite also requires unavailable `trustme`/other development dependencies. No dependencies were installed. Instead, three self-contained upstream async test functions were extracted unchanged with Python AST and executed using their actual AnyIO implementation with a 10-second outer bound per case, Linux/asyncio only:

| Exact upstream function | Result |
| --- | --- |
| `test_process_aexit_cancellation_doesnt_orphan_process` | PASS |
| `test_close_with_stdout_blocked_subprocess` | PASS |
| `test_wait_returns_on_process_exit_with_open_stdout` | PASS |

This is a **three-case source-based research probe**, not an upstream pytest suite pass, HarnessMesh integration, containment qualification, Windows/Trio proof, or provider invocation. No probe code was added to the repository. The third case closes stdin to release the grandchild; it is not proof of forcible descendant cancellation.

## Cost And Pinning

Observed physical source sizes: AnyIO `_subprocesses.py` 196 lines and `_tasks.py` 464; HTTPX `_client.py` 2,019, default transports 406 and config 248; ACP transports 118, stdio 208 and connection 276. These are inspected file sizes including comments, **not attributable reused LOC**: backend/transitive code is larger and only a subset executes. Do not sum dependency code into an inflated "80% reused" claim.

Research sizing estimate for a combined process/HTTP/ACP integration: process policy adapter 100–200 production / 200–350 tests LOC; fixed egress/stream adapter 80–160 / 150–250; one ACP session/permission adapter 100–180 / 180–300. These are overlapping alternatives to the runner/gateway estimates in the other report, not additional implementation tasks. Expected changes are policy glue; provider identity/adjudication/resolver/writer semantics are excluded and sized separately if proposed.

Use exact approved version/commit plus wheel/tarball integrity and transitive lock; never load current `main` at runtime. A release number does not bind the inspected default-branch SHA. Native runtime and provider tuple qualification must be repeated when a library or transport version changes semantics. Upstream maintainers own generic behavior and bug fixes; HarnessMesh owns wrapper policy and compatibility tests. A security or compatibility gap is a blocked tuple, not permission to substitute an unreviewed fallback.
