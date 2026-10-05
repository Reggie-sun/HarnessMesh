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

## Remaining Work

需要安装后新的有限、sealed、qualified 调查才能观察真实 subtype/timing。
一次成功的小任务不能证明长流稳定；失败不得盲目重放。若同一有界调查第二次仍没有
可用报告，保存两次 receipts/消费后按 canonical fallback 使用 named native profile 接手。
待路径隔离或真实 timing evidence 后再决定修复具体 owner；现阶段不能报告断连已修好。
