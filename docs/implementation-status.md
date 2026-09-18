# Implementation Status

## Authorization And Baseline

2026-09-19 用户明确要求“实现plan从M1到结束不要问我自己做决定”，授权实施本次读取的 M0 文档。原始文档只读冻结于 `baseline/`，其 PROPOSED 是历史状态；此处记录本轮 acceptance，不改写原始研究证据。

- Spec SHA-256: `46d17d008d64f2a4376bc58ecde866b81e9af4f70bdb3a9816d42680a11bdf39`
- Plan SHA-256: `64a65a21f4df88695f49d16b1073b8193c1f685332b049dbae6ac590e55caf35`
- Source owner: 本独立 local Git repo。无 remote、push、release、worktree。

## Scope And Ownership

Parent 拥有 contracts、supervisor、receipts、adapters、transport、capability admission、CLI、安装与最终验证。Bounded native worker 仅拥有 `src/agent_subagent_router/resolver/` 与 `tests/contract/test_resolver.py`。旧 MiniMax runner 与原 global/project configs 不变，无自动 fallback。Inspector 不运行 project scripts；外部 worker 不产生 parent acceptance。

Focused checks 为 `python -m pytest -q`，显式 native loopback conformance 单独运行。Codegraph 与 tool_search 在当前 callable registry 均不存在；精确源码与 subprocess/HTTP probes 提供证据，未声称完成 codegraph indexing。

## Qualification Ledger

| Milestone | Current evidence |
| --- | --- |
| M1a | installed Claude 2.1.77 loopback probe: worker high correct; deep max downcast to high, route mismatch; live credential absent |
| M1b | fresh bwrap uid-map probe failed with Permission denied; project admission blocked |
| M2 | implementing finite core/receipts |
| M3 | implementing resolver/snapshots |
| M4 | native adapter under conformance |
| M5 | implementing upstream identity and broker negative tests |
| M6 | blocked until containment qualified |
| M7 | corpus offline replay pending; 8 project live holdouts blocked |
| M8 | depends on qualified read-only route; unavailable |
| M9 | depends on qualified read-only route and different runtime; unavailable |

## Proof Boundaries

缺凭据不推断用户无账号或无 entitlement。无改动 host policy/sysctl；无 project-data live 调用。M1a trusted CLI route-only probe 不提供恶意 runtime containment 证明。Fake identity 不计 live identity。M2–M5 的离线实现可以在 M1b 阻塞时继续。
