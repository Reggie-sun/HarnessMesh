# MiniMax Generation Rejection Diagnostics

## Goal And Evidence

用户继续优化M5-D2A。最新真实receipt `9d17dda4-948e-42bf-bc8d-c943f9f8aca7` 的响应只记录IMAGE_GENERATION_LIMIT，无法区分cap echo、usage类型或旧有限cap超限；body已按规则隔离，不能补推断字段。当前新请求generation_tokens=null，不能把此错误称为费用上限。官方[Responses reference](https://platform.minimax.cn/docs/api-reference/responses-create)没有保证回显max_output_tokens；不依据猜测改变validator。

## Contract And Boundaries

唯一minimax_image_wire validator保留全部原条件和error code，仅增加固定allowlist拒绝标签：CAP_ECHO_NULL、CAP_ECHO_INVALID、CAP_ECHO_MISMATCH、INPUT_USAGE_INVALID、OUTPUT_USAGE_INVALID、OUTPUT_OVER_CAP。未知detail仍不保存；不保存字段值、类型的原始对象或拒绝正文。原broker在完整secret检查后独占投影标签，错误输出仍隔离为hash/长度/分类/静态标签。没有新credential/route/qualification owner。

不修改cap、null兼容、usage真实性、身份、storage、工具、隔离或no-replay条件；旧finite及unrestricted PASS/FAIL行为不变。GPT目录无精确6.1sol不自动alias或切换。正式actor、holdout及产品门不变。

## Verification And Execution

先red-green覆盖六标签、原错误分类、合法usage/null cap/有限超限、broker只投影static detail、任意detail和跨字段secret仍隔离。Full offline及明确native/containment、Ruff/diff后按base§9判断Risk Gate；纯固定metadata未改变准入时不因新增文档或API信号机械添加reviewer。通过后clean官方安装，核对source/entry/Skill及新tuple实际OS/native八图。显式一次新probe live诊断；不重放旧probe或自动追加至通过。若只有runtime拒绝而无足够根因，诚实INCOMPLETE。

## Self-Review

Parent按当前任务修复/安装授权接受本窄diagnostic合同，未要求重复许可或伪称用户逐字批准SHA。旧结果、历史request/review计数及已认可视觉效果保持；不以新诊断字段签资格。Native mapper只读负责不重复的cap/usage分支核对，不能成为blind actor；CodeGraph服务当前不含独立router仓库，实际调用以源码/测试为准。
