# Git 提交规范 (Git Commit Convention)

为了保持项目历史的清晰和可追溯性，Polaris 采用 [Conventional Commits](https://www.conventionalcommits.org/) 规范，使用中文作为主要语言。

## 提交格式

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

### Type (类型)

| Type | 说明 |
|------|------|
| `feat` | 新功能 (Features) |
| `fix` | 修补 Bug (Bug Fixes) |
| `docs` | 文档修改 (Documentation) |
| `style` | 代码格式 (不影响代码运行的变动) |
| `refactor` | 重构 (既不是新增功能，也不是修改 bug 的代码变动) |
| `perf` | 性能优化 (Performance Improvements) |
| `test` | 增加测试 (Test Improvements) |
| `ci` | 持续集成、脚本自动化及 GitHub Actions 的变动 |
| `chore` | 构建过程或辅助工具的变动 (Build Process/Auxiliary Tools) |

### Scope (范围)

Scope 应该说明修改的影响范围，优先从用户视角选择。

- `agent`: Agent 系统相关逻辑，包括思考决策、主从协作逻辑等
- `memory`: 记忆系统相关，偏好记忆等存储与召回逻辑
- `skill`: 技能系统相关、在本项目中类似插件
- `api`: 如果仅改动了后端接口路由，则使用此scope
- `core`: 如果此次改动是纯粹的底层升级，则使用此scope
- `ui`: 前端 UI 组件
- `community`: 社区治理、贡献指引、许可协议及项目管理相关的非技术文档
- `build`: 构建系统、启动脚本、部署配置及依赖更新。

### Subject (描述)

- 推荐使用“动词 + 宾语”的形式描述核心改动（如 新增...、修复...、优化...）
- 简明扼要，直接说明改动核心。
- 结尾不加句号。

---

## 保持提交纯净

我们提倡每个提交尽量只做一件事，这有助于：
1. **独立回滚**：如果一个功能出了问题，可以轻松撤销而不影响其他部分。
2. **易于代码审查**：审阅者可以更清晰地理解你的逻辑变化。
3. **清晰的历史记录**：方便后续排查问题。

如果你的改动涉及多个模块且目的不同，请尽可能拆分成多个提交或 PR。
