# 多 Agent 团队协作平台 MVP 设计规格（V1）

> 目标：从 0 到 1，12 周交付可上线 MVP。  
> 基线：Issue-first 协作 + Runtime 执行 + Skill 复用 + 可观测治理。  
> 日期：2026-04-28

---

## 1. MVP 范围（In Scope）

## 1.1 必须交付（P0）

1. 工作区与权限
   - Workspace 创建
   - 成员邀请
   - RBAC（Admin / Member / Viewer）

2. Issue 协作闭环
   - 创建、指派、评论、状态流转
   - 人和 Agent 共用评论流
   - Issue 与 Task 一对多关联

3. Agent 执行闭环
   - 创建 Task
   - Runtime 领取与执行 Task
   - 日志/进度事件回传
   - 完成后自动写回 Issue

4. Skill v1
   - Skill 创建/编辑/版本
   - Agent 绑定 Skill
   - 执行前自动注入 Skill 文本上下文

5. 最小治理
   - 审计日志
   - Token 管理（用户 token / runtime token）
   - 失败告警（站内）

## 1.2 不在 MVP（Out of Scope）

- 多模型成本优化策略（仅保留基础模型选择）
- 跨工作区共享 Skill 市场
- 自动化触发器全家桶（仅预留 cron/webhook 接口）
- 复杂审批流（仅保留高危操作二次确认）

---

## 2. 角色与核心用户故事

## 2.1 角色

- Admin：配置平台、管理成员、审计。
- Member：创建任务、指派 Agent、查看结果。
- Viewer：只读访问。
- Agent：执行任务并产出评论。
- Runtime：领取任务的执行节点。

## 2.2 用户故事（MVP Top 10）

1. 作为 Member，我可以创建 Issue 并 @Agent，让它开始处理。  
   **验收**：Issue 进入 `in_progress`，生成 Task。

2. 作为 Runtime，我可以领取属于自己能力范围内的 Task。  
   **验收**：claim 成功后 Task 状态变 `running`。

3. 作为 Member，我能在 Issue 中实时看到任务日志。  
   **验收**：日志事件 3 秒内可见。

4. 作为 Agent，我完成后可自动回复总结和产物链接。  
   **验收**：Issue 评论自动追加总结。

5. 作为 Admin，我可查看审计日志知道谁做了什么。  
   **验收**：支持按 actor/object/time 检索。

6. 作为 Admin，我可吊销 runtime token，阻止节点继续执行。  
   **验收**：吊销后 claim 全部失败。

7. 作为 Member，我可给 Agent 绑定 Skill，提高输出稳定性。  
   **验收**：执行输入上下文包含 Skill 内容摘要。

8. 作为 Member，我可将 Issue 状态切换到 blocked 并 @负责人。  
   **验收**：状态变更写入 activity_log。

9. 作为 Member，我可查看任务失败原因与重试次数。  
   **验收**：task 页面显示失败分类和 retry_count。

10. 作为 Viewer，我可只读查看项目看板和任务状态。  
    **验收**：无写权限 API 返回 403。

---

## 3. 系统设计（MVP）

## 3.1 逻辑组件

- `web`：Next.js，SSR + SPA 混合。
- `api`：FastAPI（或 NestJS，二选一，不混用）。
- `queue`：Redis + BullMQ（Node）/ Celery（Python）。
- `db`：PostgreSQL。
- `runtime-daemon`：本地 agent runner（HTTP 长轮询）。
- `object-store`：S3/MinIO。

## 3.2 部署拓扑（建议）

- 单集群部署 API + Web + Worker。
- Redis、Postgres、MinIO 独立 Stateful 服务。
- Runtime 运行在开发者本地机器（或专用 runner VM）。

## 3.3 关键时序：Issue 到完成

1. `POST /issues` 创建 Issue。
2. `POST /issues/{id}/assign` 指派 Agent。
3. API 创建 Task -> 推入队列。
4. Runtime `POST /runtimes/{id}/claim` 领取任务。
5. Runtime 执行并 `POST /runtimes/{id}/report` 回传事件。
6. API 聚合事件写 `task_event`。
7. 完成后 API 自动发 Issue 评论并结束 Task。

---

## 4. 数据模型（DDL 草案）

```sql
create table workspace (
  id bigserial primary key,
  name text not null,
  created_at timestamptz not null default now()
);

create table member (
  id bigserial primary key,
  workspace_id bigint not null references workspace(id),
  user_id text not null,
  role text not null check (role in ('admin','member','viewer')),
  unique(workspace_id, user_id)
);

create table issue (
  id bigserial primary key,
  workspace_id bigint not null references workspace(id),
  title text not null,
  description text,
  status text not null check (status in ('todo','in_progress','blocked','done','failed')),
  assignee_type text,
  assignee_id bigint,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table task (
  id bigserial primary key,
  workspace_id bigint not null references workspace(id),
  issue_id bigint not null references issue(id),
  agent_id bigint,
  runtime_id bigint,
  status text not null check (status in ('queued','running','blocked','done','failed','cancelled')),
  priority int not null default 50,
  retry_count int not null default 0,
  input_json jsonb,
  output_json jsonb,
  queued_at timestamptz,
  started_at timestamptz,
  finished_at timestamptz
);

create index idx_issue_ws_status_updated on issue(workspace_id, status, updated_at desc);
create index idx_task_ws_status_priority on task(workspace_id, status, priority, queued_at);
```

---

## 5. API 合同（最小可用）

## 5.1 Issue

- `POST /api/issues`
- `GET /api/issues`
- `GET /api/issues/{id}`
- `POST /api/issues/{id}/assign`
- `POST /api/issues/{id}/comments`
- `POST /api/issues/{id}/transition`

## 5.2 Runtime

- `POST /api/runtimes/register`
- `POST /api/runtimes/{id}/heartbeat`
- `POST /api/runtimes/{id}/claim`
- `POST /api/runtimes/{id}/report`

## 5.3 Skill

- `POST /api/skills`
- `GET /api/skills`
- `POST /api/agents/{id}/skills/{skillId}:attach`

---

## 6. Agent Skills 流程落地（平台内置）

MVP 只实现最关键的 4 个阶段门禁：

- `spec_ready`：必须有验收标准（至少 3 条）
- `plan_ready`：必须拆分子任务（至少 3 个）
- `in_test`：必须附测试证据（日志/截图/测试输出其一）
- `in_review`：必须存在总结评论 + 风险说明

状态机：

`draft -> spec_ready -> plan_ready -> in_build -> in_test -> in_review -> shipped`

当条件不满足时，transition 返回 `422` 并给出缺失项。

---

## 7. 非功能需求（SLO）

- Issue 列表 API P95 < 300ms
- Task claim 延迟 < 2s
- 日志事件可见延迟 < 3s
- 任务成功率（MVP 目标）> 85%
- Runtime 心跳中断检测 < 90s

---

## 8. 迭代计划（按 Sprint）

## Sprint 1（周 1-2）

- Workspace/RBAC
- Issue CRUD
- 基础 UI 看板

## Sprint 2（周 3-4）

- Task 状态机
- Runtime 注册/心跳/claim/report
- 日志事件链路

## Sprint 3（周 5-6）

- Skill CRUD + Agent 绑定
- 执行前上下文注入
- 失败重试策略

## Sprint 4（周 7-8）

- Agent Skills 阶段门禁
- 审计日志页面
- 失败告警

## Sprint 5（周 9-10）

- 稳定性修复
- 指标看板
- E2E 用例

## Sprint 6（周 11-12）

- 上线演练
- 回滚预案
- 文档与交接

---

## 9. 上线准入（Go/No-Go Checklist）

- [ ] P0 用户故事全部通过
- [ ] API 覆盖率 > 70%
- [ ] 至少 8 条 E2E 稳定通过
- [ ] 关键告警（runtime 离线、任务堆积）可触发
- [ ] 审计日志可追溯关键动作
- [ ] 回滚演练完成

---

## 10. 下一步（本周可执行）

1. 确认技术栈：FastAPI vs NestJS（二选一）。
2. 建仓库目录：`apps/web` `apps/api` `apps/runtime` `packages/shared`。
3. 初始化数据库迁移与 4 张核心表（workspace/member/issue/task）。
4. 先跑通一条 Happy Path：创建 Issue -> Agent 完成 -> 自动评论。

> 先把闭环跑通，再做复杂优化。
