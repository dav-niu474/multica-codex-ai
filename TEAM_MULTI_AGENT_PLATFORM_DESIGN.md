# 团队协作型多 Agent 平台落地设计（参考 Multica + Agent Skills）

> 目标：基于 `multica-ai/multica` 的产品思路，补全**可实施**的工程设计，支持团队在 8~12 周内启动 MVP。  
> 更新时间：2026-04-28

> 配套文档：`MVP_DESIGN_SPEC.md`（包含用户故事、DDL、API 合同、Sprint 计划）。

---

## 0. 执行摘要

如果只做三件事，请先做：

1. **Issue-First 协作内核**：所有任务都在 Issue 中流转，人和 Agent 共用一个协作对象。
2. **控制面 / 执行面解耦**：Server 管理协作与调度，Runtime/Daemon 在本地执行代码。
3. **Skill 资产化**：把高频任务沉淀为可版本化 Skill（模板、检查清单、工具绑定）。

这三项完成后，平台会从“聊天工具”进化为“团队生产系统”。

---

## 1. 参考工程分析：Multica 的可迁移价值

### 1.1 产品层启发

Multica 的优势不在“单次回复质量”，而在**团队操作系统化**：

- Agent 是工作区内可管理成员，而非外挂机器人。
- 任务（Issue）是协作中心，而非聊天记录。
- 自动化（Autopilot）与手工协作共享同一上下文。

### 1.2 架构层启发

可迁移的结构模式：

- **Control Plane（云端/自托管）**：身份、权限、任务编排、审计、通知。
- **Execution Plane（本地 Runtime）**：真正执行 CLI、读写仓库、调用工具。
- **Capability Plane（Skill/MCP）**：复用策略、标准动作、外部工具连接。

### 1.3 组织层启发

Multica 的关键是“能被团队治理”：

- 任务分配有责任归属。
- 过程有日志与审计。
- 经验能沉淀为可复用能力。

---

## 2. 融合 Agent Skills 的方法论（用于开发落地）

你提到的 `addyosmani/agent-skills` 适合拿来做**工程过程约束**。建议把它作为平台内置工作流，而不是仅做参考文档。

## 2.1 生命周期映射（建议内置到产品）

把 Agent Skills 的阶段映射到平台任务流水线：

- `/spec` → 产出需求规格（目标、边界、验收标准）
- `/plan` → 拆成小任务（可验证、可回滚、可交付）
- `/build` → 小步实现（一条任务一个可运行增量）
- `/test` → 证据化验证（测试/日志/截图/报告）
- `/review` → 代码质量门禁（风格、复杂度、安全）
- `/ship` → 发布与回滚策略（版本、监控、告警）

## 2.2 平台化实现建议

为每个 Issue 增加 `workflow_stage` 字段：

- draft → spec_ready → plan_ready → in_build → in_test → in_review → shipped

每阶段绑定：

- 必填产物（如 spec 文档、测试报告）
- 自动检查（例如未附测试不能进入 review）
- 负责人（人或 Agent）

这样你们得到的是“能执行、能卡点、能追责”的流程系统。

---

## 3. MVP 系统架构（可直接开工）

## 3.1 组件图（文本版）

1. **Web App（Next.js）**
   - Issue 看板、任务详情、评论流、Agent 运行日志。
2. **API Server（NestJS/FastAPI）**
   - 鉴权、RBAC、Task 编排、Skill 管理、审计日志。
3. **Queue（Redis + BullMQ/Celery）**
   - 异步执行、重试、超时、优先级。
4. **PostgreSQL**
   - 协作对象 + 执行对象 + 审计对象。
5. **Runtime Daemon（Go/Rust/Node）**
   - 本地执行代理，轮询任务，流式回传状态。
6. **Object Storage（S3/MinIO）**
   - 附件、日志归档、产物快照。

## 3.2 核心交互时序

1. 用户创建 Issue，并 @agent 指派。
2. Server 创建 Task，放入队列。
3. Runtime 拉取可执行 Task，进入 running。
4. Runtime 执行并持续上报 `task_event`（log/progress/status）。
5. 完成后生成总结评论 + 产物链接。
6. Issue 状态更新为 done / blocked / failed。

---

## 4. 数据库表结构草案（PostgreSQL）

以下是 MVP 足够的 14 张核心表：

### 4.1 协作域

- `workspace(id, name, plan, created_at)`
- `member(id, workspace_id, user_id, role, status)`
- `project(id, workspace_id, name, key)`
- `issue(id, workspace_id, project_id, title, description, status, priority, assignee_type, assignee_id, workflow_stage)`
- `comment(id, workspace_id, issue_id, actor_type, actor_id, body, created_at)`
- `activity_log(id, workspace_id, actor_type, actor_id, object_type, object_id, action, metadata, created_at)`

### 4.2 执行域

- `agent(id, workspace_id, name, model, capabilities_json, status)`
- `runtime(id, workspace_id, name, host_label, health, capabilities_json, last_seen_at)`
- `task(id, workspace_id, issue_id, agent_id, runtime_id, status, priority, input_json, output_json, queued_at, started_at, finished_at, retry_count)`
- `task_event(id, workspace_id, task_id, event_type, payload_json, created_at)`
- `session_state(id, workspace_id, issue_id, agent_id, runtime_id, session_key, context_digest, snapshot_uri, updated_at)`

### 4.3 能力与安全域

- `skill(id, workspace_id, name, version, scope, content_md, status)`
- `agent_skill(id, workspace_id, agent_id, skill_id, enabled)`
- `token(id, workspace_id, token_type, subject_id, hashed_token, expires_at, revoked_at)`

### 4.4 关键索引建议

- `issue(workspace_id, status, priority, updated_at desc)`
- `task(workspace_id, status, priority, queued_at)`
- `task_event(task_id, created_at)`
- `activity_log(workspace_id, created_at desc)`

---

## 5. API 设计草案（OpenAPI 级别）

## 5.1 Issue 协作接口

- `POST /api/issues`：创建 Issue
- `GET /api/issues?status=&assignee=`：列表筛选
- `GET /api/issues/{id}`：详情（含 task 摘要）
- `POST /api/issues/{id}/comments`：评论（人/Agent）
- `POST /api/issues/{id}/assign`：指派成员或 Agent
- `POST /api/issues/{id}/transition`：流转 workflow_stage

## 5.2 Agent 任务接口

- `POST /api/tasks`：创建任务（通常由 Issue 触发）
- `POST /api/tasks/{id}/cancel`：取消任务
- `GET /api/tasks/{id}/events`：任务事件流
- `POST /api/runtimes/{id}/heartbeat`：runtime 心跳
- `POST /api/runtimes/{id}/claim`：runtime 领取任务
- `POST /api/runtimes/{id}/report`：runtime 回传日志与状态

## 5.3 Skill 与治理接口

- `GET /api/skills` / `POST /api/skills`
- `POST /api/agents/{id}/skills/{skillId}:attach`
- `GET /api/audit-logs`
- `POST /api/tokens` / `DELETE /api/tokens/{id}`

---

## 6. 调度策略（AgentOps 实战）

## 6.1 调度评分函数（建议）

对每个 runtime 计算得分：

`score = capability_match*0.4 + security_fit*0.2 + load_health*0.2 + cost_efficiency*0.2`

选择得分最高者执行。

## 6.2 失败分级

- `RETRYABLE`：网络、429、瞬时资源不足 → 指数退避重试
- `BLOCKED`：权限不足、缺少密钥、依赖损坏 → 标记 blocked 并 @owner
- `FATAL`：逻辑不一致、数据破坏风险 → 立即中止并告警

## 6.3 SLA 与超时

- queued 超时：> 5 分钟告警
- running 超时：按任务类型设置（10~60 分钟）
- 心跳超时：> 90 秒视为 runtime 不可用并回收任务

---

## 7. 前端信息架构（IA）

建议 6 个顶层页面：

1. **Dashboard**：今日任务、失败率、平均交付时长
2. **Issues**：看板/列表双视图
3. **Issue Detail**：评论流 + task 时间线 + 产物
4. **Agents**：Agent 配置、技能绑定、健康状态
5. **Runtimes**：节点可用性、能力、负载
6. **Skills**：技能库、版本、启用范围

Issue 详情页要有三栏：

- 左：任务描述与阶段
- 中：会话与评论
- 右：执行日志、状态、产物链接

---

## 8. 安全与合规基线

1. Token 分层：用户令牌、runtime 令牌分离。
2. 密钥最小暴露：按 task 临时注入，任务结束即销毁。
3. 审计全覆盖：issue 变更、task 执行、skill 发布全部落日志。
4. 多租户隔离：任何查询默认带 `workspace_id`。
5. 高危动作二次确认：删除 skill、修改 autopilot、权限升级。

---

## 9. 12 周实施计划（可排期）

## Week 1-2：底座

- 用户与工作区、RBAC
- Issue/Comment 基础 CRUD
- PostgreSQL 与迁移脚手架

## Week 3-4：任务系统

- Task 状态机
- Queue + worker
- Runtime heartbeat/claim/report

## Week 5-6：协作闭环

- Issue 详情时间线
- 评论与任务联动
- 失败告警与订阅

## Week 7-8：Skill 系统

- Skill CRUD
- Agent 绑定 Skill
- 执行前上下文注入

## Week 9-10：流程治理

- workflow_stage 流转门禁
- `/spec` `/plan` `/build` `/test` `/review` `/ship` 阶段产物校验

## Week 11-12：上线准备

- 审计导出
- 基础看板（成功率/耗时/重试率）
- 灰度发布 + 回滚演练

---

## 10. 交付物清单（Definition of Done）

发布 MVP 前必须有：

- 架构图（组件图 + 时序图）
- OpenAPI 文档
- DB Schema 与迁移脚本
- 关键流程 E2E 用例（至少 8 条）
- 安全清单（令牌、密钥、审计）
- SLO 面板（任务成功率、平均时延）

---

## 11. 风险与缓解

1. **风险：Agent 结果不可控**  
   缓解：强制阶段门禁 + 必须附验证证据。

2. **风险：Runtime 不稳定**  
   缓解：心跳检测 + 自动回收 + 幂等重试。

3. **风险：技能污染（低质量 Skill）**  
   缓解：Skill 版本化 + 发布审批 + 回滚机制。

4. **风险：团队只用聊天不用流程**  
   缓解：关键功能仅通过 Issue 流转触发，不直接裸聊执行。

---

## 12. 结语

基于 Multica 的参考工程，你们最应复制的是“协作系统思想”；  
基于 Agent Skills，你们最应引入的是“工程过程纪律”。

两者结合后，平台会从“会写代码的 Agent”升级为“可治理的团队生产线”。
