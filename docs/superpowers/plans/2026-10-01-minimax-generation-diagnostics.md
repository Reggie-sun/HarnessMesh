# MiniMax Generation Diagnostics Implementation Plan

## Goal And Scope

按[Spec](../specs/2026-10-01-minimax-generation-diagnostics.md)把已有generation拒绝分成六个固定标签，以一次新真实诊断定位原因；不修改已有资格或finite/unrestricted接受条件。Parent独占writer，current working tree无外来router改动；Jianji外来staged/dirty保留，不创建worktree。

## Milestones

1. 在原minimax_image_wire及原wire/broker tests实现并验证标签，保留CAP_ECHO原复合判断的同等拒绝范围，分别区分usage输入/输出非法和旧cap超限；不保存原字段。Red必须证明诊断缺失，green证明原classification/secret/no-publish行为保持。
2. Fresh focused/full offline及明确native/containment、Ruff/diff，Parent核对所有changed lines及base§9 Gate，原accepted owner绑定Spec/Plan SHA与证据；stable checkpoint仅提交本任务路径，官方安装并验证所有source/entry/Skill、原config新pins及独立native/14OS证据。
3. 用原canonical ConnectionStore临时安全reference发起一次新sealed随机八图诊断；删除临时Key并保留原配置。保存receipt真实分类与标签，无自动重试/切换/额外输出；原因充分时才另行设计有依据的兼容修复，否则记录INCOMPLETE和具体blocker。GPT目录及正式truth-vs-review门独立，不启用产品。

## Acceptance And Self-Review

Spec全部标签、兼容/秘密/冻结/一次性/产品边界均有明确owner和验证；不制造mock视觉PASS。完成需要工程安装证据与该次真实诊断结果，真实视觉或M5-D2A资格只有原全门满足才可声称。Plan不是停止点；费用政策保持unrestricted，timeout/bytes/Docker/no-replay仍执行。
