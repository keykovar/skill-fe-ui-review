# FE UI Review

面向 Codex、Cursor 等支持 Agent Skills 的工具，将 Figma 设计与实际 UI 进行可追溯对比，输出视觉证据、差异说明和修复方案。

## 当前能力

- **UI Review**：默认只读，检查布局、字体、颜色、素材、页面状态及可比性。
- **UI Fix**：获得明确修改授权后修复 UI，并按原比较条件重新采集和验证。
- **Web**：使用已有的浏览器能力采集真实页面（LIVE），或复用真实组件及固定数据的本地夹具（FIXTURE）。
- **iOS / Android**：接收已有截图并记录设备、缩放和内容区域；尚不包含模拟器、ADB 或真机自动控制。
- **批量比较**：显式映射多个页面、状态和设备配置，单个案例阻塞不丢弃其他案例。
- **可视化报告**：参考图、实际图、叠加图、差异图、对比板，以及支持拖动比较、筛选和下载的离线 HTML。
- **证据记录**：SHA256、图片尺寸、环境、遮罩、阈值、采集来源与可选的 ICC / sRGB 归一化。
- **设备预设**：10 种通用 Web / iOS / Android 尺寸配置，不代表真机覆盖。

入口：[SKILL.md](skills/fe-ui-review/SKILL.md)。

## 安装

先克隆仓库：

```bash
git clone https://github.com/keykovar/skill-fe-ui-review.git
```

安装单元是 `skills/fe-ui-review` 整个目录，不能只复制 `SKILL.md`。

Codex 可让内置的 Skill 安装器安装：

```text
请使用 skill-installer 安装 GitHub 仓库 keykovar/skill-fe-ui-review 中的 skills/fe-ui-review。
```

Cursor 可将该目录放入个人 Skill 目录 `~/.cursor/skills/fe-ui-review`，或项目目录 `.cursor/skills/fe-ui-review`。

安装后重新加载对应工具；在对话中明确使用 `fe-ui-review`。Figma 与浏览器工具需要在宿主环境中另行配置，本仓库不提供登录凭据，也不自动安装工具或依赖。

## 使用示例

只读对比：

```text
使用 fe-ui-review，比较以下 Figma 精确节点与网页。
Figma：https://www.figma.com/design/FILE/NAME?node-id=123-456
网页：https://example.test/page
视口：390×844，DPR 1；英文；浅色；已登录的默认状态。
先检查数据、字体和页面状态是否可比，再展示差异图、结论和修复方案。
不修改业务代码，不自行设置验收阈值。
```

授权修复：

```text
使用 fe-ui-review 修复上述报告中已确认的 UI 差异。
仅修改指定项目的页面组件和样式；保留其他改动。
使用相同设计、数据、环境、裁剪、遮罩和阈值重新采集，展示修复前后对比。
```

多个 Figma 节点与多个页面必须逐项明确对应，不自动生成所有组合。单个设计分组包含多个状态时，先确定具体画板与页面状态。

## 本地脚本

图片比较脚本需要 Python 3.10+ 与 Pillow。Web 采集器是 Node.js ES module，需要宿主已提供并授权的 Ego Browser Page；它不会自行启动浏览器、登录或导航业务流程。

以下命令在仓库根目录执行，使用已具备 Pillow 的 Python 环境：

```bash
# 查看通用设备预设
python3 "skills/fe-ui-review/scripts/run_suite.py" --list-devices

# 只校验批量清单，不读取图片或生成报告
python3 "skills/fe-ui-review/scripts/run_suite.py" \
  --suite "/absolute/path/suite.json" --validate-only

# 比较已采集图片，输出到新的目录
python3 "skills/fe-ui-review/scripts/run_suite.py" \
  --suite "/absolute/path/suite.json" \
  --output-dir "/absolute/path/new-report"
```

清单示例：[example-suite.json](skills/fe-ui-review/assets/example-suite.json)。其中零差异阈值仅用于展示严格配置，不是通用验收标准；图片路径需要替换成自己的采集结果。

详细约定：

- [案例与比较条件](skills/fe-ui-review/references/case-contract.md)
- [Web 真实页面与组件夹具采集](skills/fe-ui-review/references/web-collection.md)
- [批量执行器、设备预设与报告](skills/fe-ui-review/references/batch-runner.md)
- [报告与修复闭环](skills/fe-ui-review/references/report-contract.md)
- [Web / iOS / Android 平台适配](skills/fe-ui-review/references/platform-adapters.md)

## 验证

```bash
python3 -B -m unittest discover -s "tests" -p "test_*.py"
node --test "tests/test_capture_web.mjs"
```

这些测试验证工具行为与比较契约，不能代替真实页面或设备验收。

## 判定边界

- `PASS`、`FAIL`、`INCONCLUSIVE` 分别表示满足条件、存在失败项、证据或约定不足。
- 没有明确验收阈值时可以测量差异，但不能据此判定通过；差异像素比例不是 UI 还原率。
- 批量执行器只处理准备好的本地图片，不负责获取 Figma、认证、页面导航或完整 UI 验收。
- LIVE 与 FIXTURE 分别出结论；组件夹具通过不能代替真实站点通过。
- 同一 Figma 画板不证明所有尺寸、浏览器、iOS 与 Android 都能零像素一致。
- 提交、推送、部署、基线更新及依赖安装均不包含在 UI Fix 的默认授权内。

公开仓库仅包含通用 Skill、脚本和测试。历史报告、账号数据、截图及项目专用适配器保留在本地，不随仓库发布。
