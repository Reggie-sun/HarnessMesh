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

## Responses Lite Correction

上述 first candidate 在 clean commit bbf09348d45f52ee33988e52bda7580cb84cffe5 官方安装后，probe d5d6245f-6668-45af-829d-f3983367e969 的实际 fake-only Docker native conformance 4c112824-79fc-4ee6-afcb-7ebd798f65a5 被 IMAGE_PROJECTION_MISMATCH 拒绝；14 OS checks true、container_removed=true、provider_requests=0。旧结果保留，没有调用该 probe 的 catalog 或 live。两次 fake-only structure/context 诊断显示五项 Lite input 及两个额外控制 fragment，不是上游能力请求。

原 classic Astra 假设被实际结构推翻。Parent 在原 Spec 增加精确 Responses Lite 修订并 Self-Review 接受当前 SHA 0b58e1963b73037c1b13a18f01ed671cfb07558ee5e2af2cf68c6a44718ef3ac；旧 SHA 为历史 first candidate，不替换其失败。Native mapper 只允许精确 schema、五项顺序、无工具、全部 sealed 图片，并机械移除两个精确哈希的基础设施控制 message。原 native 和实际 provider 字节分别保存 hash，投影版本与移除项 positions/IDs/hash/count 可追溯；不自动接纳未知 runtime prompt 或修改模型 metadata。Rust client.rs 的 Lite 分支还要求 parallel_tool_calls=false；初版受控 fixture 沿用 true 被后续 source review 发现，未当成验收，按相同范围修正。Native 验证后仍须完整审阅两段真实控制文本，再读取 credential 或执行 account/live。

最终修订 native source candidate：wire e1cf5f04aeec9a6e079db26e6aff4b072bb8966b8f2cfd7fad3ae8658bed6382，tests ec21750942865ef0235eb9527b89c476846f5feedfc02ff630a8def4fed54fc6，完整 binding 在 router-lite-candidate-snapshot.json。worker false/true 纠正先可靠 RED（2 failed/30 passed），再 Astra 33 PASS、相关 wire 197 PASS；Parent 完整当前 offline suite **1076 passed / 35 skipped**（13.97s），完整 diff 已复查。受控投影测试使用明确 synthetic 控制字串及临时测试 hash，不代表实际 runtime 控制消息已通过；真实 native 仍须独立核验。

Parent 对 material wire revision 重新评估 canonical §9：KIMI_REVIEW_NOT_REQUIRED。没有新 endpoint/credential/state/authority owner，实际 provider input 仅保留原 sealed system/user/PNG 和空 tools，未知控制 fragment 不能穿过精确 SHA、位置、shape 与 ID 门；新增工具、上下文、PNG、ref 或 legacy 漂移有负例和旧回归。尚缺 native/live 是下一步可执行资格证据，不以 review 替代；未发现 critical consequence 的新增路径或重大后果加未解决工程缺口的组合。用户计划禁止 Kimi 保持，read-only native mapper 只提供结构证据，Parent 独立裁决和验收。
