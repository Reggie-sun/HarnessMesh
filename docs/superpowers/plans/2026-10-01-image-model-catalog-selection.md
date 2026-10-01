# Image Model Catalog Selection Implementation Plan

## Goal and Scope

实现 [Spec](../specs/2026-10-01-image-model-catalog-selection.md) 的一次目录投影，沿已有 `subscription_account.py` / `cli.py` owner；不改型号 whitelist、generation、资格或凭据归属。

## Milestones

1. 在 `tests/unit/test_subscription_model_catalog.py` 验证默认兼容、显式投影、目录缺失/超限/非法 slug/重复和非 GPT、绑定 gate 及零 quota/generation；先 RED 再实现原 owner 的受限投影和 CLI flag。
2. 原 model/account/budget/security tests 及完整 offline suite；Parent 审阅最终 diff 并按 §9 判断风险，保存 exact snapshot、Spec/Plan SHA 和结果。必要的 read-only reviewer 依用户禁 Kimi 与既有 native fallback。
3. stable commit 后按官方安装 owner 安装核验，冻结一个全新 owned probe、运行 native conformance，再显式一次 catalog-only discover。保存真实 canonical receipt 与安全投影，不重放旧 probe；失败记录实际 blocker，仍不执行 generation 或自动换型号。

## Self-Review

每个 Spec 约束分别由纯 projection tests、CLI negative gate、原 credential/once regression 与真实目录 receipt 覆盖。真实目录成功仅支持下一次精确选型冻结，整个 M1 尚需视觉资格；开发测试和安装不替代它。保留原历史 refs 和失败，不扩大生产路径。
