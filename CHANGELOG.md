# 更新记录

## 0.1.0 — 2026-10-29

首个公开版本，提供 Figma 与实际 UI 的视觉对比工作流。

采用 [MIT 许可证](LICENSE)，安装目录中同时保留许可声明。

### 功能

- UI Review 默认只读；UI Fix 在明确授权后修复，并要求重新采集验证。
- Web 支持通过已有 Ego Browser Page 采集 LIVE 页面或真实组件 FIXTURE。
- iOS / Android 支持已有截图输入、设备元数据及内容区域记录。
- 支持单案例和显式映射的批量比较，以及 10 种通用设备尺寸预设。
- 生成参考图、实际图、叠加图、差异图、对比板、JSON / Markdown 和离线 HTML 报告。
- 保留原图、SHA256、阈值、遮罩和采集来源，支持显式 ICC / sRGB 归一化。
- 提供 Codex / Cursor 安装说明与 38 项本地工具测试。

### 验收范围

- 批量执行器比较准备好的本地图片，不负责 Figma 获取、登录和业务页面导航。
- 尚不包含 iOS / Android 模拟器或真机自动控制。
- 未设置验收阈值、页面状态不符或证据不足时返回 INCONCLUSIVE。
- 像素指标不等同于完整 UI 验收；FIXTURE 结果不能代替 LIVE 验收。
- 公开版本不包含项目专用夹具、历史报告、真实账号数据或设计素材。

### 安装与使用

见 [README](README.md) 和 [Skill 入口](skills/fe-ui-review/SKILL.md)。
