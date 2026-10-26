# AI-APF

**发布时验证状态：macOS／Windows 跨平台 CI 尚未完成。** 本机 macOS 的脚本测试已运行；Windows 原生脚本测试及真实 Windows Codex 宿主触发仍待验证。后续结果以 [GitHub Actions](https://github.com/KKEERB/ai-apf/actions/workflows/tests.yml) 为准。

AI-APF 是一个帮助研究者和 Codex 共同澄清任务、形成科研问题并选择下一步的 skill。目标明确的任务可以直接处理；研究意图或证据条件不清楚时，它帮助辨别关注点、比较必要的选择，并保留研究者的判断权。

它可以解释概念、检查证据与结论的边界、设计有限检查，并在需要时建议合适的执行环境。AI-APF 是可持续改进的协作方法，现有行为测试不证明它必然提高科研收益。

## 安装

需要 Git、Codex 和 Python 3.9 或更高版本。以下方法将 skill 安装到用户级 `~/.agents/skills/ai-apf`；复制前会检查常用用户级目录，避免默默覆盖现有副本。如果已有 AI-APF，请先检查其位置和版本，决定如何升级。还应检查当前项目的 `.agents/skills` 是否已有同名 skill：Codex 不会把同名副本合并。

### macOS / Bash

在准备保存仓库的目录运行：

```bash
git clone https://github.com/KKEERB/ai-apf.git && {
  apf_dest="$HOME/.agents/skills/ai-apf"
  apf_codex_home="${CODEX_HOME:-$HOME/.codex}"
  if [ -e "$apf_dest" ] || [ -e "$apf_codex_home/skills/ai-apf" ]; then
    printf '%s\n' 'AI-APF already exists; inspect the installed copy before upgrading.'
  else
    mkdir -p "$HOME/.agents/skills" && cp -R "ai-apf/skills/ai-apf" "$apf_dest"
  fi
}
```

### Windows / PowerShell

在准备保存仓库的目录运行；示例使用 Python Launcher（`py -3`），也可以使用本机实际的 Python 3 命令。

```powershell
git clone https://github.com/KKEERB/ai-apf.git
if ($LASTEXITCODE -ne 0) { throw 'Clone failed; no installation was performed.' }
$apfCodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$apfDest = Join-Path $HOME '.agents\skills\ai-apf'
$apfOther = Join-Path $apfCodexHome 'skills\ai-apf'
if ((Test-Path -LiteralPath $apfDest) -or (Test-Path -LiteralPath $apfOther)) {
  Write-Host 'AI-APF already exists; inspect the installed copy before upgrading.'
} else {
  New-Item -ItemType Directory -Force -Path (Join-Path $HOME '.agents\skills') | Out-Null
  Copy-Item -LiteralPath (Join-Path (Get-Location).Path 'ai-apf\skills\ai-apf') -Destination $apfDest -Recurse
}
```

原生 Windows 与 WSL 的用户目录、`CODEX_HOME` 和宿主环境可能不同：请在实际运行 Codex 的环境中安装和启用，不要假定两个环境共享配置。

## 使用

在支持技能的 Codex 客户端选择 **AI-APF**，或在对话中输入 `$ai-apf`。Codex 也可以根据任务描述按需选择该 skill；自动选择并不等于 Plan 默认入口已启用。如果新技能没有出现，可按客户端提示重新加载或重启。

普通任务不需要填写科研问卷。例如，请它直接处理一次单位转换；对于尚未成形的研究直觉，可以请它先帮助分辨关注点、解释必要概念，再决定是否需要资料或一个有限检查。

## 可选：在 Plan 模式默认使用

此选项会更改所选 `AGENTS.md` 或 `AGENTS.override.md`，适用于希望每次进入 Plan 时考虑 AI-APF 的用户。先阅读当前有效的指令文件并检查作用范围：非空同层 `AGENTS.override.md` 会覆盖 `AGENTS.md`；项目指令也可能改变结果。选用当前有效文件，避免新建 override 而隐藏原有指令。

示例针对用户级 Codex home；如要仅作用于项目，改为该项目的有效指令文件。执行前确认 skill 与目标路径确实属于当前宿主。

### macOS / Bash

```bash
apf_codex_home="${CODEX_HOME:-$HOME/.codex}"
apf_skill="$HOME/.agents/skills/ai-apf/SKILL.md"
apf_script="$HOME/.agents/skills/ai-apf/scripts/configure_plan_entry.py"
apf_agents="$apf_codex_home/AGENTS.md"
python3 "$apf_script" status --agents-file "$apf_agents"
python3 "$apf_script" enable --agents-file "$apf_agents" --skill-file "$apf_skill" --dry-run
# 检查预览与目标文件后执行：
python3 "$apf_script" enable --agents-file "$apf_agents" --skill-file "$apf_skill"
```

### Windows / PowerShell

```powershell
$apfCodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$apfSkill = Join-Path $HOME '.agents\skills\ai-apf\SKILL.md'
$apfScript = Join-Path $HOME '.agents\skills\ai-apf\scripts\configure_plan_entry.py'
$apfAgents = Join-Path $apfCodexHome 'AGENTS.md'
py -3 $apfScript status --agents-file $apfAgents
py -3 $apfScript enable --agents-file $apfAgents --skill-file $apfSkill --dry-run
# 检查预览与目标文件后执行：
py -3 $apfScript enable --agents-file $apfAgents --skill-file $apfSkill
```

如果有效文件是已有 `AGENTS.override.md`，先检查它，再将 `apf_agents` 或 `$apfAgents` 改为该文件的实际路径。脚本只管理自己的标记区段，改变已有文件前创建备份；重复执行是幂等的。状态或预览不写文件。遇到链接、覆盖或权限冲突时先处理报错，不绕过限制。

在新会话的真实 Plan 模式中检查技能是否被读取；输出中的 `host_activation: not_verified` 表示脚本本身无法验证宿主加载。**AI-APF 不修改模型、推理深度、权限，也不安装 hook。**

关闭默认入口时，在同一终端、使用与启用时相同的目标路径运行：

```bash
python3 "$apf_script" disable --agents-file "$apf_agents"
```

```powershell
py -3 $apfScript disable --agents-file $apfAgents
```

关闭只移除管理区段，仍可显式使用 `$ai-apf`。不要直接用旧备份覆盖后来新增的用户指令；需要恢复时先比较内容。

## 验证与限制

仓库配置了 macOS 和原生 Windows、Python 3.9 与 3.13 的 CI 矩阵；**公开发布时矩阵尚未完成**，实际结果请看仓库 Actions 的对应运行。本机 macOS 的脚本测试已经运行。Windows 原生脚本测试以及真实 Windows Codex 宿主中的技能发现与 Plan 触发仍待验证；自动化文件操作测试不能替代该宿主检查。不同 Codex 客户端和版本的行为可能不同。

科研任务中，请区分已核实事实、研究者判断、模型推断和待检验假设。脚本运行、图像或一次检查的成功不自动证明科学结论；最终研究方向与科学判断由研究者决定。

## English quick start

AI-APF is a Codex skill for adaptive task clarification and scientific problem formation. Clone this repository, copy `skills/ai-apf` to your user-level `.agents/skills/ai-apf` directory, then invoke `$ai-apf` in Codex. Check for an existing copy first; see the macOS and Windows commands above.

An optional Python helper adds a managed Plan-mode block to a selected effective `AGENTS.md` or `AGENTS.override.md`. Inspect the existing file and use `status` and `enable --dry-run` before making a change; use `disable` with the same target to remove the block. The helper does not change model or reasoning settings, install hooks, or verify host activation.

At publication, the configured macOS and native Windows CI matrix has not yet completed. Local macOS script tests have run; native Windows script tests and Codex discovery and Plan activation on a real Windows host remain unverified. See the Actions link above for subsequent CI results. Scientific benefit remains to be evaluated on real research tasks.

## License

MIT. See [LICENSE](LICENSE).
