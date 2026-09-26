# Deep Entitlement Age Limit Removal

Date: 2026-09-26

## Authorization And Change

用户在获知 Kimi 失败来自本地路由的 24 小时资格观察期限后，明确要求开子代理去掉该限制。本轮由 Native TDD worker 修改 validator/tests，Parent 审查、同步 Q2 和安装；没有删除账号、凭据、containment、预算或请求身份门槛。

`validate_entitlement()` 删除 `age <= 86400`，保留 `age >= 0`、可解析且带时区的观察日期，以及既有 kind/source/credential_match/tier/context 校验。错误文案从 fresh 改为 valid。`project_run.verify_smoke()` 沿用该唯一 validator，无第二资格分支。

Q2 的旧 24h 条款按当前用户明确变更指令同步；历史整份 Spec 的 SHA 批准保留，未冒称用户重新批准全部新 bytes。该 bounded 行为目标已明确，实施按 RED → validator 最小修改 → focused/full offline → Parent review → 受管安装顺序执行。

## Verification

- 新增 validator 和真实 `verify_smoke` 调用路径测试：旧观察（7 天、10 年）可用；未来、无效、无时区日期及缺失/错误资格字段仍被拒绝。
- Focused：19 passed。完整 offline：212 passed、12 skipped；skipped 不计为 native/live conformance。
- Parent 重新读取原 qualification `4f2d5dc8-4234-4665-b382-e82f1ad6cc00` 的 account evidence，源码 validator 离线通过。原 bytes 不变，SHA-256 为 `1d5fcc89abfe8e1d48df2c8b97bf7f0da2d1b726fe7fd51c88d9261a430e6b1c`；未刷新日期或读取 credential。
- Installed CLI 初检绑定不可变旧 snapshot，源码修改本身不会自动生效；安装结果将在下方记录。

## Parent Risk Decision

本次 final candidate 为本文同 commit 的 source/tests/Q2 窄变更；精确 staged tree 与 source snapshot 可由该 commit 重开。`KIMI_REVIEW_NOT_REQUIRED`：用户要求子代理实现，未另要求 Kimi implementation review；变化只移除用户明确否决的时间上限，旧凭据、route、evidence 类型和权限约束仍在。具体后果是历史订阅观察不再按年龄被本地拒绝；不产生凭据泄露、跨项目写入或 durable-state 损坏路径。此条件与 project admission 已有确定性测试，未发现具有重大后果且需要额外模型 review 的验证缺口。Parent 已审查全部 diff；没有把 tests 或 worker 结论作为远端账号状态证明。

## Boundary

取消 TTL 不保证远端订阅永不失效。远端实际拒绝、credential fingerprint 不匹配或其他 route 身份失效仍按原逻辑处理。此次没有 live Provider request、没有新资格 smoke、没有改写历史 receipt、没有 push/release。
