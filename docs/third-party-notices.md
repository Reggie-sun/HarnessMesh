# Third-Party Decisions

## Reuse

本轮复用 reviewed prior art 的边界与测试思路：shinpr/sub-agents-skills 的 immutable invocation/builder seam、AGPair 的 process/report/receipt 分离、wshobson 的 native asset projection、agent-harness 的 managed output hashes。没有直接 vendor/fork/copy 它们的 implementation；不将新代码宣称为已复用上游代码。固定 commits 与 MIT license evidence 保留在 [research](baseline/research/global-cross-model-subagent-landscape.md)。

直接抽取 shinpr 小模块仍需带入 `_constants`、`_loader`、权限 registry、旧 dialogue 状态及 env inheritance；它不能保留此项目的隔离/receipt contract。故只复用接口形状与回归思路，不引入整包依赖。

## Runtime

本机原 Claude Code 2.1.77 在 fake native probe 将 max 降成 high。独立安装 `@anthropic-ai/claude-code@2.1.277` 及其固定同版本 `@anthropic-ai/claude-code-linux-x64` optional dependency；使用 `npm --ignore-scripts`，直接执行包内 native binary。原 binary/global config 不改。

该 runtime 是 Anthropic 专有发行物，不是 MIT 项目；license 标示 `SEE LICENSE IN README.md`，包内 LICENSE 指向 Anthropic terms。只作本机可替换 runtime，不将 binary 复制进此 Git repo。binary SHA-256 为 `722210f05ba494d8f6df69423c4d4f2960900f7a007d0532851c7a36e375cab7`；wrapper package npm integrity 为 `sha512-JedQvDxaHIWr303Ymlqlz43j3LqRaUe7rNtDKjEDQaHt8MkKPpCR+jKI6K0TKU5gquTqodgYLfTNM3qfGkTbpQ==`。隔离安装目录中的 package-lock.json 固定完整 distribution integrity。

## Sandbox And HTTP

没有添加 sandbox-runtime：其 Linux 基础仍是 namespaces/bwrap，不能解决本机 uid-map 拒绝。最终用已有普通Docker作OS隔离（network none、非root、drop capabilities、read-only root/source）；实际adversarial probes通过，未修改host sysctl或采用privileged模式。HTTP使用Python标准库fixed-host HTTPSConnection，关闭自动连接重开、不读取环境proxy、不跟随redirect、无orchestration retries。未增加provider SDK或gateway dependency。

## Gemini

独立安装官方 `@google/gemini-cli@0.60.0`，Apache-2.0，Node 22.21.0；其package-lock及LICENSE保留在本机隔离安装，不vendor到此Git repo。源码接口参考官方Gemini CLI的stream-json events、tools registry、Code Assist envelope、native context loader。OAuth public client ID/secret constants来自同版本bundle（非用户secret），真实refresh前验证bundle中精确常量；没有复制上游auth workflow、onboarding或fallback实现。

固定完整package tree和Node hash；Gemini CLI 0.60.0会将旧Flash alias升级为3.5，故parent显式选择 `gemini-3.5-flash`，broker只允许该exact path/model并核验upstream `modelVersion`。旧alias、不明identity或替代model均拒绝。当前只资格化read-only工具；selected Skills缺少native activation证明，明确fail closed。
