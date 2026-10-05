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

## Remaining Work

原长流问题仍未解决；需在相关失败再次发生时检查新增 subtype/timing，或做已授权的
同 host 路径隔离。网络规则文件的 same-file ownership/修改选择仍等待用户回复：
A 允许保留原修改并只追加 `api.kimi.ai` DIRECT 验证；B 不改网络；C 先继续只读取证。
本轮没有修改 VPN file、shared selector 或 authenticated endpoint，也没有追加第三次
Kimi attempt。旧失败和原消费不重置。本调查仍不能报告断连已修好。
