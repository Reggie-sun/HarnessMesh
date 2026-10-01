# Image Model Catalog Selection

## Goal and Authority

简辑完整自动轮廓任务的用户明确允许核验并选择应用独立账号实际支持图片的 GPT 型号。任务内必要合同修订按当前 global 规则由 Parent Self-Review 接受；这是本次授权下的窄修订，不声明用户另行批准了未知文件 SHA。

## Contract

在原 `observe-image-subscription --verify-model` 加显式 `--discover-models`，仅新 seal 绑定本文件 exact SHA 时可返回目录投影。仍由原 credential owner 读取应用独立账号、固定 HTTPS catalog endpoint、一次 GET、原每 probe 永久 reservation、Docker conformance 与 sealed snapshot 核验。不得读全局登录、查询 quota、refresh、generation、恢复旧 ledger 或复用已消费 probe。

投影仅输出精确 GPT slug、匹配数量及显式 text/image modalities；限制目录最多 128 项、slug 最多 80 个 ASCII 字符并匹配 `gpt-[a-z0-9][a-z0-9.-]*`。非法目录拒绝，非 GPT 项不投影，重复 slug 不得声明支持图片。不返回 display_name、instructions、account 字段或原始响应；原 credential reflection 防护保留。模型可用性及 catalog 原字节 SHA 绑定 canonical receipt。默认无 discover flag 时原 receipt shape 不变。

该投影不授权请求任意型号、不成为视觉资格或发布 authority；实际选型必须冻结新精确模型合同后再执行能力探针。旧模型 whitelist、unrestricted 策略、image route 和 capability 判据均不在此修改。

## Acceptance and Self-Review

一次 catalog GET 能提供安全的候选型号证据，默认兼容、非法/重复/超限/secret 反射 fail closed；未绑定修订、缺 verify flag 或合并 recovery 时零 GET。独立投影保持 authority=none/eligible=false，目录 READY 不替代真实视觉。Parent 核对 scope、旧语义、数据最小化和 owner 后接受本窄合同。
