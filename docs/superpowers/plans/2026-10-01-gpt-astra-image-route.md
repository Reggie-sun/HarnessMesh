# GPT Astra Image Route Implementation Plan

## Goal and Scope

实现 [Spec](../specs/2026-10-01-gpt-astra-image-route.md) 的精确新 tuple，复用原隔离订阅图片路线，不开放任意型号。

## Milestones

1. `image_contract.py` 提供绑定本 Spec SHA 的精确 tuple 检查并沿原 unlimited policy；`subscription_account.py` / `cli.py` 只接受 sealed task 证明的新型号；`codex_image_wire.py` 按 Responses Lite 修订严格验证并仅移除两个固定基础设施消息。新增 `tests/unit/test_gpt_astra_image_route.py` 覆盖正确/缺ref/错误 tuple、旧兼容、零查询负例及准确 wire 字段，先 RED 后 GREEN；原 native 假设失败及新 native/actual 摘要分别保存。
2. 相关 model/catalog/budget/wire/security tests 及全 offline suite；Parent stable diff/self-review 与 §9 Risk Gate、实际 source snapshot；官方安装及 binding 检查。
3. 冻结全新 probe 和原判断标准，实际 Docker native conformance 后只读取该 probe 一次目录；能力成立才显式一次真实八图 probe。任一步失配保存 receipt 并停止，不换模型、补 quota、refresh 或复用旧 probe。

## Self-Review

此改动仅由账号真实图片清单支持的精确型号扩展既有路线；catalog projection、sealed tuple、wire 校验和真实能力各司其职。维护旧失败、历史 refs 和生产 guard。外部能力不可由测试或目录替代，不把新模型支持写成全 M1/M4/M5 完成。
