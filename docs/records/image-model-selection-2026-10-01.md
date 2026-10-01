# Image Model Selection Record — 2026-10-01

## Current Fixed-Model Receipt Followthrough

简辑用户最新约束只允许精确 `gpt-6.1-sol` / `gpt-6-luna`，含本地fake、能力及正式请求；本文件下方Astra选择、Lite和非空工具诊断均为历史，不继续该路线。已有固定型号conformance分别 `eda8f663-8dfe-4531-967f-aa269b422254` / `11bbba2a-89d9-4eaf-a49c-1a4646df56f6` 均ENGINEERING_CONFORMANCE_COMPLETE、tools=[]、8图、14项OS检查、provider_requests=0。

随后各一次认证目录receipt `7e05275d-3f3a-485a-86b7-7dc2219564cc` / `a7a518aa-5aad-49b5-8ef0-5740fa02f79d` 均INCOMPLETE：7项、精确匹配0、image未证明，两响应SHA `a6c8e85904c4816ca11c2e86e7fb8a03498322aa69dcc28ca0d58941bb7d2a02`相同。原始filtered artifact与全部列出SHA/size已重新核对，没有重发GET或读取全局登录。证据根沿用 `auto-contour-full-20261001-51kctk6d`；本次只读audit在 `auto-contour-catalog-followthrough-20261001/catalog-receipt-audit.json`。这不是远端永久不支持结论，也不是实际图片能力。

Jianji bundled版本、REST client_version与User-Agent均0.154.0；应用model/list的hidden过滤不用于Router `_model_facts` 的exact slug匹配，因此不能解释这两份REST记录的零匹配。没有证实实现或目录来源缺陷，不修改matcher、model metadata、alias、credential/once/seal门。固定型号目录准入及可信正式execution仍INCOMPLETE，actual image/formal requests0，PRODUCT_DISABLED；[Jianji AI record](../../../jianji/docs/shape-matched-cover-m5d2a.md#fixed-model-catalog-followthrough--2026-10-01) 独占项目语义/材料状态。Astra旧runtime工具失败不继续充当当前固定型号的native blocker。

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

## Actual Nonempty Tool Boundary

上述 Lite source 在 clean commit 5c8dae0e70532f030b66f7fd7ec8f0c8e42ae3eb 官方安装后，新的 probe 33e0f4cf-d07f-4d95-bef8-b785f68ce21e/native conformance 555f7756-236f-4a26-87c7-b320998efc8e 仍为 IMAGE_NATIVE_EXECUTION_INCOMPLETE；native invocation 56b0c29c-687f-4af3-ac32-cc6242a7f265 在 IMAGE_CONTEXT_MISMATCH 拒绝、wire/provider=0、container_removed=true。实际 native 并非空工具：fake-only 完整诊断 07fe73fb-7dcd-49e8-af84-1870c5d6481f 列出 exec/wait/request_user_input_async 及六个 collaboration tools。先前结构摘要从缺失的 top-level tools 推算 toolsCount=0 是不充分的推断，不能当作 input[0].tools=[] 的事实。

Parent 完整审阅了两个控制 message，均只是2429/271字符的通用 runtime root/team控制文本，精确 SHA 与合同一致，未发现任务/账号秘密；但是仍不能接纳工具。真实 prefix at_/system msg_ 使用 UUIDv5（而非本修订暂定v7），control/user 为v7；当前严格拒绝保持，不凭测试 fixture 推导 native 合格。实际二进制 app-server help 与 exact argv/config features-list 均在原 Docker owner 内读取，provider0：code_mode/code_mode_host/multi_agent/multi_agent_v2=false，仍不能证明实际 tool router 为空；unified_exec=true 的 effective 差异也未解释。首个 help 的非规范 CODEX_HOME 被entry拒绝、features-list的不存在home错误保留，修正成原driver的私有规范home后得到有效只读结果。

只读 Rust mapping 找到原配置遗漏：agents.enabled=false 可覆盖 catalog multi-agent version，current_time_reminder 与 code_mode_only 需独立关闭。Parent 在原 baked native driver及同源fake RPC owner 加这三个显式设置，保持模型、endpoint、credential、无工具拒绝、取消与预算；不剥除非空工具集、不修改 model metadata。后续新 snapshot/镜像/探针仅验证此受支持设置，若仍有工具则必须继续拒绝；app-server没有已经证明的全局 thread tool allowlist，不能把“禁用若干flags”称为隔离证明。

该四行配置修正的 Parent fresh offline suite 为1076 PASS/35 SKIP（13.85s），最终 diff 仅三个显式禁用值及本记录；native效果仍NOT_EVALUATED。stable Risk Gate不触发：权限只收紧，原非空工具拒绝先于credential，尚无工具执行、上游请求或发布；实际隔离的缺口由下一次新image/native诊断检验，不声称已解决。Kimi禁止及全部原source/once/credential gates保持。

## Installed Native Result and Effective Configuration

配置修正已在 clean commit `d632e16703c85939f17d827d180df5f5f6bdf5d3` 官方安装，source_dirty_at_install=false，installed source hash `c13dd7daade61b16a7d70b184b1c802e2872cd252c4596625715bc3aa0081d8e`。使用同一已核对的本地 runtime（0.154.0、SHA `3188814c35471432d4123203e0eb38e5bddc60226e3d7ddf0e59e649ea140022`）重建原 Docker owner，image `1e92bf56073e25ce217ad8707c9b8fb2cb94d595fc1a089aacce8e8af0d5d745`；没有 pull、替换旧镜像配置或读取账号凭据。

新 probe `5dc8ac29-637b-4345-87d7-8138b3ed56f2`、canonical native conformance `4de80ccf-cfce-49a5-8684-f0c53c31ae9b`、native invocation `f46e63e5-df1a-4a5f-9bc6-b3775d115e5a` 的结果仍为 **IMAGE_NATIVE_EXECUTION_INCOMPLETE**，14 OS checks true、container_removed=true、wire/provider requests=0。一次 fake-only 完整结构观察 `eaaa5591-e6b4-4493-b793-ee9e5efb9667` 确认 `agents.enabled=false` 实际移除了六个 collaboration tools 及两段额外控制消息；现在 input 为三项，仍暴露 `exec`、`wait`、`request_user_input_async`，prefix/system IDs 仍为 UUIDv5。原五项/v7/空工具 mapper 正确拒绝，未放宽为接受该请求。

进一步仅在该镜像的原 sandbox.execute/source=None 中运行 baked fake RPC。receipt `09253a11-096e-4bac-ad7a-d628a595ac00` 的同进程 `config/read` 显示 code_mode/code_mode_only/code_mode_host/multi_agent/multi_agent_v2/current_time_reminder/unified_exec=false，agents.enabled=false，orchestrator skills/mcp=false；实际假服务仍收到请求。此前 CLI features-list 的 unified_exec=true 不能替代同进程 app-server config，也不再用于断言本请求的 effective flag。各设置已传入不等于 model tool router 为空。

`--strict-config` 诊断分开保存：baked diagnostic 自带 `model_max_output_tokens` 被拒绝（receipt `46b3e933-e685-4af5-ba9f-b775c33ee207`，fake requests0），该值不在正式 native driver 中；换用正式 `image_codex.argv_for` 的精确参数、仅追加 strict-config 后，receipt `fc5227e8-ec4e-49d5-890d-ccbf678f5532` 没有 configuration/RPC error、fake requests1。不能把前者当作正式 driver 的错误，也不能把后者当作空工具或视觉资格。首个 effective-config 诊断结束后因错误使用 runs 的父目录作为 ReceiptStore 而未持久化，保留该 orchestration 失败；改用既有私有 runs 后取得上述正式诊断记录。所有这些诊断均 provider0，没有账号目录 GET、generation、auth refresh 或 quota 请求。

当时只读源码mapping未找到已经证明适用于该Astra二进制路径的thread-local全工具关闭参数；model metadata tool_mode优先级只是待核对解释。Astra这项历史失败保持，不剥除工具定义、改metadata或绕过native门。**该历史checkpoint停止于Astra runtime no-tools阻断**；固定两型号之后已通过native conformance，当前目录/image和正式execution缺口见本文件首节。旧probe不重放、MiniMax NOT_QUALIFIED不重写，没有完整M1或语义资格。

此补充只更新 durable record，未修改已验证的 executable source；不将1076项 offline tests重标成此次重跑或 native acceptance。原安装、source、Spec 与receipt绑定由 Parent 再核对；后续语义修复须重新验证、clean安装及新的 probe。记录保存于私有 `auto-contour-full-20261001-51kctk6d`，没有适用的额外 capture skill，也未写外部memory。
