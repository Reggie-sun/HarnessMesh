# MiniMax Unset Cap Compatibility

## Evidence And Goal

本轮installed新probe `b4cd4d6f-f60b-4eb7-add5-4692b02950b4`、qualification `6c849d7a-1a2b-4d0f-8c5a-99da9acf3ef0`、native `bb1d3b8e-09f0-4e36-90be-e43c3b3b6da0` 的唯一真实请求HTTP200/2775bytes，固定diagnostic `CAP_ECHO_NULL`。请求generation_tokens=null、wire省略max_output_tokens。原正文隔离、Key删除，旧失败不改。官方[Responses reference](https://platform.minimax.cn/docs/api-reference/responses-create)将max_output_tokens定义为可选请求参数，没有要求响应回显；null事实来自本次receipt而非文档猜测。

## Contract

新selected_refs绑定本Spec exact SHA时，且已获接受的spending_policy=unrestricted和generation_tokens=null同时成立，允许响应max_output_tokens=null，表示无可验证数值回显，绝不表示某个有限上限已执行。有限合同、旧seal、缺ref/错ref、任何boolean/zero/negative/string/object echo继续原拒绝。正整数echo和省略字段沿用已有行为；usage仍须非负整数，所有身份/store/completion/secret/工具/structured output及原raw/native关联门保持。

原wire owner独占校验，broker/decoder复用，不建立新transport、credential或资格owner，不改发出的请求。原失败仅摘要保留，不升级资格或重放原probe。GPT精确模型缺失仍阻断；产品和formal资格不受本修复影响。

## Verification And Execution

Red-green覆盖新null接受、旧unrestricted和finite拒绝、错ref与非法echo、非法usage及broker实际响应关联/秘密隔离。Fresh full offline/native/containment、Ruff/diff和base§9一次Risk Gate、clean官方安装、新pins八图/14OS通过后，仅一次新sealed真实验证修复；不得重放、换model或循环直到通过。其他新拒绝须调查具体证据，不捆绑未知兼容放宽。

## Self-Review

Parent依据用户持续优化/修复安装授权接受该窄修订；不伪称用户逐字批准SHA。有限金额/token限制已被用户撤销，null未设置上限的响应不应伪装超限；旧门和所有真实资格条件仍保存。本修订不是降低truth-vs-review标准。
