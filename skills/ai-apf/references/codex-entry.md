# Codex 入口与启用

仅在用户要求配置、检查或停用本 skill 的入口时使用本文件。普通任务不要修改用户配置。以下产品接口核对日期为 2026-10-23；目标客户端存在差异时核对其实际文档与能力。

## 先确认目标环境

1. 确认当前工具实际运行在哪台机器、哪个工作区，能否访问用户希望配置的 Codex。云工作区的保存成功不等于用户 Mac 已安装。
2. 确认 `ai-apf` 已在目标环境可发现，定位其真实 `SKILL.md`。避免安装同名副本。官方当前本地发现目录包括用户 `~/.agents/skills` 和项目 `.agents/skills`；平台管理的技能按其实际入口使用。
3. 确认真实 Codex home：配置了 `CODEX_HOME` 时使用该目录，否则通常为 `~/.codex`。只读取必要的相关配置，不输出凭据。
4. 检查该层的 `AGENTS.override.md`、`AGENTS.md` 及相关项目约定。非空 override 会使同层普通 AGENTS 不生效，不要另建 override 屏蔽已有指令。

入口范围只考虑 Codex；GPT 可以是工作路由建议的外部目的地，不配置 GPT skill 入口。

## 显式与默认入口

- 显式入口：在支持的技能选择器中选择 AI-APF，或使用 `$ai-apf`。核对实际选择/读取记录，不能只凭模型说“已启用”。
- 隐式匹配：`agents/openai.yaml` 允许按描述匹配；该设置本身不是 Plan 自动触发器。
- Plan 默认入口：在有效 AGENTS 文件中合并一个短管理段。该段要求在宿主明确处于 Plan 时使用主 skill，已有内容可复用，科研等引用模块按需读取。
- AGENTS 规则在新 run/session 初始化时读取，项目规则可覆盖全局规则；配置后用新线程验收，不假设旧线程立即更新。

## 配置脚本

使用随 skill 附带的 `scripts/configure_plan_entry.py`，需要 Python 3.9 或更高版本及标准库。下面示例假设 skill 安装在用户级 `.agents/skills/ai-apf`，目标是用户级 Codex home 的 `AGENTS.md`。先检查实际宿主、已安装位置、`CODEX_HOME` 和有效指令文件；若假设不符，替换为确认过的真实路径，不要把云端或其他系统的路径写进本机配置。原生 Windows 与 WSL 各有自己的宿主、路径和配置。

macOS / Bash：

```bash
apf_codex_home="${CODEX_HOME:-$HOME/.codex}"
apf_script="$HOME/.agents/skills/ai-apf/scripts/configure_plan_entry.py"
apf_skill="$HOME/.agents/skills/ai-apf/SKILL.md"
apf_agents="$apf_codex_home/AGENTS.md"
python3 "$apf_script" status --agents-file "$apf_agents"
python3 "$apf_script" enable --agents-file "$apf_agents" --skill-file "$apf_skill" --dry-run
# 检查预览并确认目标文件后：
python3 "$apf_script" enable --agents-file "$apf_agents" --skill-file "$apf_skill"
```

原生 Windows / PowerShell（`py -3` 也可替换为已确认的 Python 3 命令）：

```powershell
$apfCodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$apfScript = Join-Path $HOME '.agents\skills\ai-apf\scripts\configure_plan_entry.py'
$apfSkill = Join-Path $HOME '.agents\skills\ai-apf\SKILL.md'
$apfAgents = Join-Path $apfCodexHome 'AGENTS.md'
py -3 $apfScript status --agents-file $apfAgents
py -3 $apfScript enable --agents-file $apfAgents --skill-file $apfSkill --dry-run
# 检查预览并确认目标文件后：
py -3 $apfScript enable --agents-file $apfAgents --skill-file $apfSkill
```

用户已授权该范围的启用时，完成只读检查和预览后执行，不重复要求批准。若目标是当前有效的 `AGENTS.override.md`，显式指定它。若只希望项目生效，使用该项目的有效 AGENTS 文件，不擅自扩大为全局。

脚本只管理 `ai-apf:begin/end` 段，保留其它内容；改动前备份，幂等执行不重复写入。它不安装 skill、不安装 hook、不改模型或权限。Windows ACL 不等同于 POSIX 文件权限；不要把权限位当作 ACL 保证。`status` 和 `--dry-run` 不写文件。脚本报告 `host_activation: not_verified`，因为文件配置不等于宿主已经加载。

若文件访问或自动审批拒绝该修改，保留已完成工作并说明被拒操作与原因，遵守原有审批流程；不要通过替代路径、符号链接或其他命令修改同一个受保护目标。若当前无法访问目标机器，交付待执行步骤，不声称已启用。

关闭默认入口时，只移除管理段，保留显式使用能力：

```bash
python3 "$apf_script" disable --agents-file "$apf_agents"
```

```powershell
py -3 $apfScript disable --agents-file $apfAgents
```

skill 路径变化后，重新用真实路径运行 enable。不要盲目还原整个备份覆盖后来新增的用户指令；先比较差异。

## 目标宿主验收

在新会话中核对真实的技能读取/选择记录、有效指令来源以及输出行为：

| 检查 | 输入与合格表现 |
| --- | --- |
| 显式 | 用 `$ai-apf` 做简单单位转换；读取正确 skill，直接给结果。 |
| Plan 默认 | 不提 skill 名，只给普通任务；有效入口触发轻量判断，遵守 Plan 执行限制，不展开科研问卷。 |
| 按需深入 | 给一个粗糙研究直觉；需要时读科研模块，暂定理解允许纠正。 |
| 上下文 | 在已有目标、方法和数据说明后继续工作；不重新问已知信息。 |
| 模式与覆盖 | 核对实际 Plan/非 Plan 切换、项目覆盖；用户文字提到 plan 不等于宿主已切换。 |
| 关闭 | disable 后开新会话，默认段不再生效；显式 skill 仍可使用。 |

这只能验证入口和行为，不能证明真实科研收益。研究效果应比较直接任务、原有 Plan 用法与 AI-APF，并推进到共同的执行里程碑。

Windows 原生自动化文件操作测试不等于真实 Windows Codex 宿主已验证。发布时若尚无真实宿主，明确将技能发现、默认触发和权限交互标记为未验证；不要推断宿主行为。

首版不安装 hook。若实际宿主持续漏触发，再核对当前 hook 支持、信任和真实模式字段后评估，不预先增加后台逻辑。

## 官方依据

- [Build skills](https://learn.chatgpt.com/docs/build-skills)：显式/隐式使用、本地发现及元数据。
- [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)：指令加载、作用域和覆盖。
- [Hooks](https://learn.chatgpt.com/docs/hooks)：仅在需要扩展入口时查阅。
