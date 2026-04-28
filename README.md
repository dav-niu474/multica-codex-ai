# Multi-Agent Collaboration P0 (API Scaffold)

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn apps.api.main:app --reload
```

## P0 endpoints

- `POST /api/workspaces`
- `POST /api/members`
- `POST /api/issues`
- `GET /api/issues?workspace_id=<id>`
- `GET /api/issues/{issue_id}`
- `POST /api/issues/{issue_id}/assign`
- `POST /api/runtimes/register`
- `POST /api/runtimes/{runtime_id}/heartbeat`
- `POST /api/runtimes/{runtime_id}/claim`
- `POST /api/runtimes/{runtime_id}/report`
- `GET /api/tasks/{task_id}/events`

This scaffold implements the first P0 coding loop:
`Create Issue -> Assign Agent -> Create Task -> Runtime Claim -> Runtime Report -> Issue/Task status update`.
