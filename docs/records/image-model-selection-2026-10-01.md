# Image Model Selection Record — 2026-10-01

## Scope and Contract Acceptance

简辑完整 auto-contour 任务用户明确允许核验并选择应用独立账号实际支持图片的 GPT。Parent 经原应用刷新 owner 取得候选清单，选择 `gpt-6-astra / high`，未更改应用当前 `gpt-5.6-luna` 设置、全局登录或旧 probe。

任务内必要合同修订按当前 global 自动执行授权由 Parent Self-Review 接受：catalog Spec `590bab13743a463c12b55ac38eda0e4ba598df06c8cb55a386079c5658d70e56`、Astra Spec `622c3ea8c119276b837fbfa9d9bbdcff25f73f52c8dec50d24b7380cc7684570`。各自 implementation plan 指向相同 Spec。此记录不伪造用户对新 SHA 的单独回复；旧 exact accepted refs 保留。

## Implementation and Verification

原 `subscription_account.py` 可显式安全投影型号目录，`cli.py` 的新 flag 需两个 exact refs 且排除 recovery；新 Astra 只在原 image contract 的精确 tuple、高档位、unrestricted 及修订 ref 成立时接受。原 wire 保持严密订阅结构、无工具、精确 PNG 身份，其他型号和默认模型观察接口保持兼容。没有新 endpoint、credential owner 或 fallback。

新增测试先 RED 后 GREEN：目录 21 个缺能力失败；Astra 9 failed/5 passed 后实现。最终 parent 全 offline suite 为 **1061 passed / 35 skipped**（13.69 秒）；35 个 native/conformance skip 不算通过。parent focused Astra 最终 18 passed，worker catalog/订阅兼容最终聚焦 107 passed。`git diff --check` 通过。

## Review Risk Gate

stable source candidate 绑定四个 source files 和两个新增测试的实际 SHA，保存于私有 `auto-contour-full-20261001-51kctk6d/router-candidate-snapshot.json`。按 canonical §9 G2 判断为 `KIMI_REVIEW_NOT_REQUIRED`：无用户指定该 candidate 的 Kimi 审查；新投影不返回账户、display_name、instructions 或 raw catalog；原 `_get` secret-reflection、固定 host、no redirect、deadline、close 和原 once ledger 未改变。新 tuple 没有扩大凭据或发布权限，负例覆盖未接受 ref/错误 tuple/任意 alias；未发现达到 critical consequence 的新增具体路径。实际 runtime/wire 与上游图片能力的缺口由下一步 canonical native/live receipt 验证，不用工程 reviewer 冒充能力资格。

## Evidence and Limits

此 checkpoint 只证明工程实现及 offline regression。官方安装、native conformance、HTTP 目录与真实视觉 capability 各自另行取得 receipt；未满足时零 generation 或保留 NOT_QUALIFIED，不能从应用 RPC 清单推导 Router HTTP 目录相同，也不能声明完整 M1/M4/M5 已完成。正式 source execution owner 和 semantic qualification 当前仍未完成，产品保持关闭。仓库无专用 capture skill，本记录为 canonical durable implementation record。
