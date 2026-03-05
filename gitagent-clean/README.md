# GitAgent-Clon

SaaS application for cloning Git repositories, detecting AI agents, and executing them through a chat interface.

## Tech Stack

- **Backend**: FastAPI (Python 3.11)
- **Frontend**: React + TypeScript + Vite + TailwindCSS
- **Deployment**: Docker on Render

## Project Structure

```
gitagent-clon/
├── backend/
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── postcss.config.js
├── data/
├── Dockerfile
├── render.yaml
└── README.md
```

## API Endpoints

- `POST /api/clone` - Clone repository and detect agents
- `GET /api/agents/{session_id}` - Get detected agents
- `POST /api/select-agent/{session_id}/{agent_id}` - Select active agent
- `POST /api/chat` - Execute agent with message
- `GET /api/files/{session_id}` - List generated files
- `GET /api/download/{session_id}` - Download ZIP
- `DELETE /api/session/{session_id}` - Delete session
- `GET /api/health` - Health check

## Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Docker Build

```bash
docker build -t gitagent-clon .
docker run -p 8000:8000 gitagent-clon
```

## Deploy on Render

1. Connect GitHub repository to Render
2. Create Web Service with Docker runtime
3. Use `render.yaml` configuration
