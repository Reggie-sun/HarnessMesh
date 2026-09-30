# MiniMax Documented Response Identity Amendment

## Authorization And Evidence

用户继续完整验收，此前已明确授权router修复及安装。Parent依任务内合同默认授权完成Self-Review并实施本窄协议兼容修订，不要求重复批准；保留旧合同、sealed probes、receipts及消费。

新安装诊断receipt `587e7993-23f2-4c16-92b5-27a5aa5aa19c` 的一次真实8图请求HTTP200，canonical native `c427c842-fd57-4938-b18b-b89868f56d27` 确认 `REQUEST_ID_MISSING`，2775 bytes正文按原规则隔离仅留摘要。不能推断其未评估body模型或视觉内容。官方[Responses reference](https://platform.minimax.cn/docs/api-reference/responses-create)要求body `id`、`model`、`status`、`output`，没有保证 `x-request-id` / `request-id` 响应header。把不存在的header当作唯一请求关联来源是本路线的协议兼容缺口；不声称是provider缺陷。

## Identity Contract

只有新sealed task包含本Spec exact accepted SHA时允许以下兼容；旧task仍必须提供原header。唯一MiniMax validator继续由固定TLS broker调用，不信任worker/self-report。

header存在时，仍校验重复、非法值及多个ID冲突，不能以body绕过坏header。header完全缺失时，要求完整JSON的body `id` 符合原请求ID的有界ASCII规则，作为本次TLS响应的correlation ID，显式 `request_id_source=response-id`；不能声称provider提供了request header。不伪造header值。

此correlation仅与固定authenticated `api.minimaxi.com /v1/responses`、单次capability和one-in-flight生命周期、实际request/response SHA、sealed原PNG与prompt绑定组合使用，不能单独证明模型身份。仍要求body精确 `model=MiniMax-M3`、object=response、status=completed、store=false、无error/incomplete/工具、合法usage及全部秘密检查。body可选request_id若存在仍必须匹配所用ID，错配拒绝；不得输出model alias、迁移endpoint或猜模型revision。

broker在新合同的两种路径均记录明确ID来源、已校验的实际content-type及请求ID headers（仅该白名单），以及原request/response SHA。native decoder必须读取这些broker-owned实际headers并重验完整响应，核对来源、correlation ID和原wire hash；缺来源、缺header证据、未知来源、借用receipt、改响应字节拒绝，不合成header。显式request_id=null视作存在但不匹配，拒绝。原Codex、Kimi、human及无新ref的MiniMax合同不变。

## Qualification And Verification

新增headers持久化前必须通过现有response_secrets owner检查：content-type、x-request-id、request-id只允许最多三个可捕获字段；先核查各值及所有有界字段排列连接，阻断Key/capability跨header分段、改变顺序或Unicode转义反射。content-type证据只保存原validator已核实的normalized MIME类型，丢弃无关参数；request IDs保留已校验实际值。拒绝只存原分类/摘要/长度，不存header片段。此安全收紧不创建第二秘密检查器，也不绕过原完整body fragment检查。

先red-green验证旧missing-header拒绝、新ref缺header的documented response可绑定、invalid/conflicting/duplicate header仍拒绝、缺/坏body ID及wrong model/storage/status/工具/秘密仍拒绝、native来源与字节/ID借用拒绝。full offline/native Docker/fake、Ruff/diff后按base§9 critical身份门评审；用户禁止Kimi，沿已授权原生接手用单一named read-only reviewer，保留累计历史，最多初审和两次有依据修复复核，每次900秒。Parent裁决后clean commit、官方安装、新tuple conformance，再显式一次新sealed capability；不重放旧probe，不机械追加直到通过。

任何capability成功只证明该随机图包和新protocol/pins；formal执行owner、GPT精确目录证明、独立holdout/全片真值与产品gates仍独立。旧错误保持INCOMPLETE；所有未评估指标null/NOT_EVALUATED、authority=none、eligible=false。

## Self-Review

本修订修复已确认的header前置不兼容，通过精确accepted-ref保护旧语义，保留TLS/model/byte/one-shot/secret/tool/qualification组合，不降低视觉评分或真值门。新ID来源可审计，decoder不伪造header；scope仅原validator/broker/decoder和其tests，未建立第二identity、凭据、生命周期或源资格owner。
