# Resume Qualification

此文记录恢复阶段的历史checkpoint；最终M7/M8、Gemini blocker和安装验证见[final-qualification.md](final-qualification.md)。下列image与阶段状态不代表最终安装。

## Authorization

用户明确要求完成M1–M9，并告知Kimi key已配置在CC Switch。只读既有provider配置，私密复制至router credential store；不修改CC Switch或global Claude设置、不打印secret。

## Route Evidence

- worker smoke `fd8183cc-35ee-4b71-941a-c0309aef2db3`: PARSED，1 wire，k3-256k/high/adaptive。
- deep初次 `ea6d855a-3b22-4ab4-97fc-781c75e34460`: 403，1 wire，保留失败。
- deep显式correction `ca132501-53a2-45f9-9c7c-488395f517fc`: PARSED，1 wire，k3/max/adaptive；原403具体原因未知。
- worker qualification `27ba7e0c-32b1-41a9-8210-4f49474e0a30`；deep `4f2d5dc8-4234-4665-b382-e82f1ad6cc00`。canonical receipts位于本机private state，包含source smoke artifact与current credential fingerprint。
- 只读现有Chrome Kimi console确认Pro会员及同一credential mask；官方membership reference https://www.kimi.com/code/docs/en/kimi-code/models.html 。实际1M consumption NOT_EVALUATED。

## Containment

普通Docker image `sha256:cb9efea157119b8df762ab02e530562593d351174973999421847835314be75b`，Claude runtime SHA `722210f05ba494d8f6df69423c4d4f2960900f7a007d0532851c7a36e375cab7`。

20 OS checks、native Read正向和host/proc/Bash/Task/MCP负向、broker并发cap、cancel/timeout cleanup均有实际执行。独立reviewer_max verdict accept with concerns；资格相关24测试及key-switch零请求测试通过。SIGKILL/daemon故障恢复仍为边界。

## Experiment

M7 run set `420ae6c4-ab09-45fb-96a4-fac7d43800f2`，8任务，rubric/source在运行前冻结。M1+M7初始10任务，最多2 corrections。

第一任务 `jizhang-rules-worker` receipt `2cc2f151-0f65-4c55-b7d9-0cc72e4ded1c`：2 wires、所有required文件真实Read；REPORT_SCHEMA_ERROR（original_path字段及/work引用不满足path/source_path contract）。修正prompt显式schema，parser未放宽、原receipt不改写；使用最后一次correction，source/rubric/model/effort/budget保持不变。

## Historical Corpus

逐项查找MM-01…MM-10对应旧raw locator、sanitized report和runner诊断源码；现存证据均不足以绑定原MiniMax invocation terminal，保持UNRESOLVED_PROVENANCE。10 synthetic fixtures仅证明新router的拒绝/分类行为，不能升级历史结果为PASS。

## Verification

阶段命令 `python -m pytest -q tests/unit tests/contract tests/regression tests/conformance --native-conformance --containment-conformance`：143 passed，1 skipped（该次未设image env）；独立reviewer设置image env后143 passed无skip。随后新增key绑定/API测试及Gemini adapter5项测试分别通过；最终全量结果另记，不将阶段结果冒充最终tree。
