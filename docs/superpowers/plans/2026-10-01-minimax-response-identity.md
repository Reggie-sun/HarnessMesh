# MiniMax Response Identity Implementation Plan

## Goal And Boundaries

按[documented identity contract](../specs/2026-10-01-minimax-response-identity.md)，新exact-ref任务以真实TLS响应body ID完成correlation，同时保持精确model及全部其他资格门；旧任务和其他backend行为不变。Parent独占writer，不创建worktree、不改Jianji外来dirty。

## Milestones And Verification

1. 修改原 `minimax_image_wire.py`：exact Spec SHA gate；header合法时原逻辑，缺失时新任务才读取有界body ID；proof仅新路径明确来源。`transport/codex_broker.py`在新合同两种路径保存明确来源及已校验的真实白名单headers；`image_output.py`必须使用其重验wire response和correlation，不造header。现有wire/broker tests新增red-green覆盖新旧、字段拒绝（含request_id=null）、header冲突、缺失/错误来源与headers、source/response-ID/bytes tampering、秘密和tools门。
2. fresh focused与full offline/native+containment、Ruff/diff；绑定exact source/test/Spec/Plan和运行证据作一次required read-only native review（已授权Kimi替代，最多初审+两次有依据复核，wall900/轮）。Parent裁决并修复Confirmed，不让reviewer签资格。官方clean commit/install及installed完整性/新probe14项OS、完整8图fake证明新pins。
3. 原canonical connection安全handoff一次、新accepted-ref seal后显式一次真实8图capability，保留历史消费、不重试未知、不切换provider。结果完整记录。仅在双方路线和formal owner及M5-D2A全部准备齐备后启动原完整验收；否则诚实保存真实阻断。

## Acceptance And Self-Review

Round25/26分别确认来源降级、request_id=null及新headers分段secret反射，Parent用真实否定测试复现后修复。response_secrets原owner在capture前检查最多三项真实headers的全部有界排列；保留原body guard。Fresh full/native及最后一次有依据targeted re-review后才安装，不把前两轮finding当clearance。

修复成功需documented identity seam的可执行拒绝/通过证据、required review裁决、实际安装和canonical live结果；不能用unit、native或HTTP200宣称看图资格。旧失效不改成PASS；新source/route/config独立。Spec覆盖、owner、compatibility、no-replay、production禁止及后续次序已核对，计划不是本任务停止点。
