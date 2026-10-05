# Kimi Response-Body Investigation — 2026-10-05

## Scope And Evidence

继续处理 session `01a107ea-b425-7fe2-8764-606d9cbdecd7` 的长响应断连；
旧 invocation `7d68d310-8520-427e-b52b-854476d153bf` 与本仓库第一次调查
`17c25c00-dd42-47fb-8c41-a6562e4a3788` 仍为 `OUTCOME_UNKNOWN`，没有有效报告。
此前 `67095fe` 只修复 unknown 后隐式追加请求的本地缺口，并没有修复远端稳定性。

当前进程与 Mihomo controller 的只读证据表明：`api.kimi.ai` 解析为 fake IP，
连接实际经过 `Match → PROXY → 香港HK03`；代码忽略环境代理不等于绕过透明代理。
本机现有规则仅有 `DOMAIN-SUFFIX,kimi.com,DIRECT`，不覆盖 fixed `.ai` host。
公开 DNS 显示 `.ai` 指向 Cloudflare；未认证 HEAD 的 `.ai` response server 为
Cloudflare（HKG），`.com` 为 nginx。两者 HEAD 404 都不证明认证生成兼容或稳定性。

本轮还只读观察到其他正在运行的工作单元最终产生
`5ce7f138-c31c-4766-b945-aa93c3c92fd3`，第三次 wire request 在约 336.8 秒、
收到 1,580,270 bytes 后发生同类错误。这不算本仓库有界调查的第二次 attempt。
其他历史调用也有 338 秒的成功响应，故没有证明 universal fixed cutoff。

## Hypotheses And Missing Evidence

- Local budget：wall 3,600 / idle 1,800 / 32,000 tokens / 16 MiB 未耗尽，
  已有 receipt 排除这些额度是所述五分钟错误的直接触发者。
- Long upstream silence：只有总 duration/bytes 无法确认；需要末次收包距错误的时间。
- Active-stream reset：需要 error subtype 和最大单次 read 等待，区分持续收包被重置。
- Proxy/edge instability：有实测路由差异，但尚无同 host 的可控路径隔离结果，不能认定根因。
  网络 source 的规则文件已有其他人的未提交修改；更改前向用户请求 ownership/授权，
  不自动改共享 selector、不重启网络、不迁移 authenticated endpoint。

## Bounded Diagnostic Change

唯一 transport owner 仍为 `KimiUpstream` / `transport.diagnostics`。
保留原 `phase/kind` 与 `OUTCOME_UNKNOWN`，新增 fixed-enum connection detail；
response-body exception 只附加 bounded numeric `response_progress`：headers/body 时长、
完整已收 chunk bytes/count、末次收包距错误时间和最长单次 read 等待。
不读取/输出异常文本，不存 body/credential/hostname supplied by error，不接受 partial，
不自动 replay，不改变 identity/secret/terminal gates、model/reasoning 或 sealed budgets。
这些数字是接收观测，不是模型进度、服务端责任归属或 completion 证明。

## Verification And Risk Gate

基线 `b7c37a6`；三个 code/test paths 的 diff SHA-256
`403d475c2c9036f58794aa1f8af1ddb9cb9f45a038e6fe7ebc5b0e3fad429d04`。
五个新增断言先 RED（5 failed），实施后 focused transport `88 passed`；
Micromamba offline `1082 passed, 35 skipped`，changed-file Ruff 与 diff check 通过。
本轮未重复完整 native suite；doctor 的 Docker/native fake 隔离检查通过，不是 live identity。

Parent Gate：`KIMI_REVIEW_NOT_REQUIRED`。用户没有请求本 diagnostic snapshot 的独立
implementation review；修改不放宽 authority、凭据、付费准入或 durable state。
固定枚举和不含内容的 timing/count 由直接 RED→GREEN、transport quarantine tests 与
offline suite 覆盖，没有发现严重后果且仍存在、适合独立模型补证的重大语义缺口。
外部研究与之前失败的 Kimi 调查均不算该 snapshot 的 independent review。

## Installed Read-Only Result

Code/test/initial record commit `6b697138d385e0f698341a6e63f22b1313cc6f44` 已经官方
installer 安装；manifest source hash
`f2c60354849e0ba374f7df9e07af740c017a9302b91673e8f2d33d256c7a0da0`，
`source_dirty_at_install=false`，source/installed `broker.py` SHA 一致，entry/Skill SHA
符合 manifest。安装时另外的 research Markdown 尚未跟踪，不属于安装的 package source。
安装后的 doctor Docker/native fake containment 通过；未声称新的 provider qualification。

第二次显式 Kimi attempt 将问题缩为两个 source files，保留原调查 predecessor 与最高
finite policy；新 seal `19bf99949d4c0394fd2e0662e8cc521d78b0589b44e5d45d8721a86fb37b6f50`，
frozen set 为 home/repository AGENTS、accepted Spec 与两个 source files，全程未修改。
canonical invocation `4ca70ee3-dd96-49cd-957c-c93188d79a9d` 为 `PARSED`，
96.728 秒、两次 HTTP 200、两次 authenticated identity `k3/max`、每次 cap 32,000，
actual Read 与 report SHA
`a900da4cf422af82e1f3db5c1783add8b50b4008273f795a7ae2e0a916206f3a` 已由 CLI 机械核验。
没有自动 retry，没有满足连续两次运行失败条件，因此不触发 native fallback。

Parent 源码裁决：确认 `KimiUpstream.timeout` 交给 HTTP socket operation，没有约 300 秒
累计 body timer；Broker/supervisor 仍拥有 wall/idle/revoke 边界。新数字可区分静默与
持续收包后重置，但没有改变传输，也未在本次成功调用中产生 failure timing。
该有效小任务只完成了有界源码调查，不是 final implementation review，
`parent_acceptance=NOT_EVALUATED`；不能将它当成原长流事故已修复的证明。

官方路由/SDK/流终态研究由
[upstream research](kimi-stream-upstream-research-2026-10-05.md) 独占；
不采用其自动重试模式，不因地区文档或 HEAD 时延迁移 sealed endpoint。

## Pre-Approval Boundary

原长流问题仍未解决；需在相关失败再次发生时检查新增 subtype/timing，或做已授权的
同 host 路径隔离。网络规则文件的 same-file ownership/修改选择仍等待用户回复：
A 允许保留原修改并只追加 `api.kimi.ai` DIRECT 验证；B 不改网络；C 先继续只读取证。
本轮没有修改 VPN file、shared selector 或 authenticated endpoint，也没有追加第三次
Kimi attempt。旧失败和原消费不重置。本调查仍不能报告断连已修好。

## User-Authorized DIRECT Isolation

用户随后明确选择 A：保留现有未提交修改，仅追加 `api.kimi.ai` DIRECT 并验证。
Parent 在 VPN source template、当前安装的 rule enhancement 和运行配置各追加一行
`DOMAIN,api.kimi.ai,DIRECT`；与修改前 private recovery backups 的完整 byte diff 均仅
为该行，没有全量安装模板或重新合并 DNS/订阅配置。API host、path、TLS verification、
Kimi model/effort/caps 和 HarnessMesh package 没有改变。

`verge-mihomo -t` 成功；VPN `test_build_runtime.py` 的 16 tests 通过；controller
`PUT /configs` hot reload 为 204，没有重启 service 或主动关闭原连接。所有 Selector 的
name/now projection SHA reload 前后相同：
`12cae04b912b4654e290b630cd7df6e9914fe2506908be8b501b923831235526`。
`codex-mihomo.service` 为 active；新 HEAD 连接实际命中 `Domain/api.kimi.ai/DIRECT`，
HTTP 404、TLS 0.783 秒、total 1.427 秒。这仅证明新 route 的 reachability。

VPN commit `d830f37`（既有 `company` branch）只包含 template 的该一行；使用
`git add -p` split 排除原有 RustDesk changes。原 template 两行、DNS 三行修改和
`.gstack/` 保持未提交，不移到当前任务提交。Private recovery storage 位于
`/home/reggie/.local/state/agent-subagent-router/kimi-network-20261005-0H3G1R/`，
directory 0700/files 0600，不纳入 repo、worker projection 或 invocation artifacts。

Parent 显式创建第三次、DIRECT 后的新调查，不重放旧 unknown seal。Goal 与首次失败
调查相同，保留同五个 read paths/required evidence；source 增量为已验证诊断及 unknown
replay fence。Seal `d0621d7cad59b5f4e0a64e9ab8537219bb07bcf9c04baa69c6c37f792c7f5045`，
effective deep/k3/max/32,000、wall3,600/idle1,800/request64/output16MiB/context8MiB。
Doctor 的 fake containment 通过；live invocation 连接已由 host controller 核验为 DIRECT。
这是一次用户批准的路径隔离调查，不是 triggered final implementation review。
历史失败、成功、消费、receipts 全保留；不能由 worker 自述断言实际网络或模型身份。

## DIRECT Live Result And Parent Adjudication

Canonical invocation `17cf8e33-fe27-4a6a-b204-300f5f25088a` 为 `OUTCOME_UNKNOWN`，
process 363.440 秒、exit 1、`truncated=false`、wire requests 2、orchestration retries 0，
没有 terminal worker report。`subagent receipt` 读取并核验 artifacts；receipt exact bytes SHA
`d61cb353c988a19f583981adaf9eff01e9bb655a84768943a3d3ceadcbd527d9`。
所有八个 frozen source bytes 在调用结束后仍与 manifest SHA 一致。

第一请求 HTTP 200，14.073 秒，authenticated response identity `k3`、effort `max`。
第二请求 HTTP 200 后失败，total 348.519 秒；新诊断为
`RESPONSE_BODY / CONNECTION_ERROR / BROKEN_PIPE`，headers 7.486 秒、body 341.021 秒、
received 1,947,076 bytes、566 chunks、last-byte age 0.006 秒、最大 read wait 4.105 秒。
Controller 多次观察到该 authenticated invocation 连接实际为
`Domain/api.kimi.ai/chains=[DIRECT]`，而非原 HK03 proxy chain。
第二请求未完成 identity/terminal validation，不将第一请求的身份扩张为第二响应已验证。

Parent 源码检查：body loop 的 activity callback 仅更新 lock 内的时间和 byte count，
没有 stdout/pipe 写入；本次异常发生在 upstream response-body 路径，不是 CLI 大量日志
或 supervisor output cap 触发。supervisor reason 为 exited，wall/idle 上限均未达到；
连续实际 bytes 与 4.105 秒最大 read wait 排除本次为 1,800 秒 idle timeout。
失败后的 capability revoke 保持，无第三次 wire 请求或 unknown replay。

裁决：**DIRECT 已安装并实际生效，但原长流断连未修复**。移除原代理节点并不足以消除
该故障；不能据此断言代理节点就是根因，也不能仅凭 `BROKEN_PIPE` 归因到 provider。
DIRECT 仍经过本机 Mihomo TUN/ISP/remote edge；本次没有 packet/edge evidence 能进一步
区分这些层。新的 subtype/timing 将后续调查从“长时间无响应”缩到“持续收包后连接失败”。
本次没有确认一个可安全修复的本地代码 defect，不追加猜测性 retry、模型降级、endpoint
迁移或第四次 paid investigation。历史 consumption 与 unknown 保持；本次不是独立审查通过。

## Checkpoint And Remaining Boundary

此 A task 的单域名规则修改、config lint、16 build tests、controller reload、实际路由与
一次新 sealed live 验证已完成。Parent Gate：`KIMI_REVIEW_NOT_REQUIRED`；既有 accepted
rare-review contract 下，此精确 host-routing change 不改变 authority、TLS、凭据、model
identity、transport acceptance 或其他 Selector，直接配置与实际连接证据充分，没有另需
独立模型补证的重大语义缺口。live investigation 不冒充 implementation reviewer。

没有新 runtime implementation、Spec/Plan、refactor、push 或 release。未重新运行
HarnessMesh code suite（其 code bytes 本轮未变）；诊断安装的旧 focused/offline 证据属于
上面的既有 checkpoint。新失败不能覆盖成成功。未启动未授权 endpoint 迁移或更多调用；
后续根因修复仍需要能区分 local TUN/ISP/remote edge 的 transport evidence。

## Local Runtime Idle-Timer Repair

用户要求继续排查并修复成功。本次重新核验旧 filtered stdout：两次长调用的 Claude
terminal result 均为 `Request timed out`。因此上面的 `process.reason=exited` 只能排除
supervisor 主动按 wall/idle 终止，不能排除 CLI 内部 timer。原“未确认本地 defect”结论
是当时证据状态，不是当前结论。Native `code_mapper` 接手连续失败的同范围工程调查，
确认进程退出后的 `broker.revoke → upstream.close → socket.shutdown` 可造成
`BROKEN_PIPE`；旧 receipt 的具体竞态先后没有直接时间戳证明，不伪造远端归因。

Broker 保持完整响应身份/secret 校验后交付；这使 CLI 等待本地 broker 的 socket
无 bytes，虽然上游持续有真实接收活动。Pinned Claude `2.1.277` 使用 Bun，其 socket
idle timer 独立于此前已设置的 SDK/Claude stream timers。官方资料及其局限由
[upstream research](kimi-stream-upstream-research-2026-10-05.md#follow-up-claude-code-and-bun-idle-timers)
记录。修复仅在原 adapter 将 `BUN_CONFIG_HTTP_IDLE_TIMEOUT` 按秒向上取整对齐 sealed
`wall_seconds`；不关闭 timer，不改变总 wall/真实 upstream idle owner，不改 endpoint、
runtime binary/image、model、effort、generation cap、重试、缓冲或 acceptance。

Unit 首先因缺该环境变量 RED。Pinned runtime 的零 Provider native 因果实验保持 SDK
`API_TIMEOUT_MS=25000`，fake server 延迟 12 秒才发送 headers/完整 SSE：Bun idle=1 秒
提前 exit1/`Request timed out`；adapter 的 Bun idle=25 秒得到 exit0/`PARSED`，均只发
一次 POST、无重试。这证明当前 binary 支持该变量的秒单位，以及它独立于 SDK timer；
测试模拟 broker 完整缓冲时的首响应等待，不声称模拟收到 headers 后的 body stall。

另增加 failed-body 的固定 SSE event/count/trailing-byte metadata，帮助后续区分已收
`message_stop` 与 HTTP EOF；不持久化 raw event、payload、异常文本或身份声明，完整
stop 后连接失败仍 `OUTCOME_UNKNOWN` 并撤销。深层/非法 JSON、重复 keys、非有限数字、
UTF-8、未知 event 的 RED→GREEN 与 private-data assertions 均通过。此 metadata 不是
可接受终态，也不将 partial identity/report 交给 worker。

Fresh verification：`test_claude_timeouts.py + test_claude.py --native-conformance`
为 7 passed；完整 `pytest -q --native-conformance --containment-conformance` 为
1113 passed / 13 skipped（93.12 秒）；changed-file Ruff 与 `git diff --check` 通过。
Skipped checks 不算通过。Parent Gate：`KIMI_REVIEW_NOT_REQUIRED`：该有限 timer
对齐和 metadata 没有放宽 authority/security/unknown acceptance，直接 native 因果复现、
隔离/协议负例及 full suite 已覆盖本地语义，没有适合另一模型补证的重大剩余语义缺口。
Native mapping 不是独立 implementation review；真实长调用仍需新 installed 验证。

下一步只允许一个明确新建的 post-fix sealed live validation，保留所有 predecessor
receipts/消耗，不重跑旧 seal。它验证修复后的 route/report，不重置 review 三轮预算，
也不是向模型反复询问原诊断。安装和 live 结果须另记，不能由本地测试提前声称长流已修好。
