"""
GitAgent-Clon Backend - FastAPI Application
Versión con entornos virtuales por sesión y manejo inteligente de dependencias.
"""

import os
import json
import shutil
import subprocess
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# =============================================================================
# CONFIGURACIÓN
# =============================================================================
DATA_DIR = Path("data")
REPOS_DIR = DATA_DIR / "repos"
PROJECTS_DIR = DATA_DIR / "projects"
VENVS_DIR = DATA_DIR / "venvs"          # <-- Nuevo: directorio para entornos virtuales
SESSION_TIMEOUT_HOURS = 6
CLEANUP_INTERVAL_MINUTES = 30

REPOS_DIR.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
VENVS_DIR.mkdir(parents=True, exist_ok=True)

sessions: Dict[str, Dict[str, Any]] = {}

# =============================================================================
# MODELOS PYDANTIC
# =============================================================================
class CloneRequest(BaseModel):
    repoUrl: str

class ChatRequest(BaseModel):
    sessionId: str
    agentId: str
    message: str

# =============================================================================
# FUNCIONES AUXILIARES DE SESIÓN
# =============================================================================
def create_session() -> str:
    session_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow()
    sessions[session_id] = {
        "id": session_id,
        "repo_path": None,
        "agents": [],
        "selected_agent": None,
        "created_at": now,
        "expires_at": now + timedelta(hours=SESSION_TIMEOUT_HOURS),
        "files_generated": []
    }
    return session_id

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    session = sessions.get(session_id)
    if not session:
        return None
    if datetime.utcnow() > session["expires_at"]:
        delete_session(session_id)
        return None
    return session

def delete_session(session_id: str) -> bool:
    session = sessions.pop(session_id, None)
    if not session:
        return False

    # Eliminar repositorio clonado
    if session.get("repo_path"):
        repo_path = REPOS_DIR / session["repo_path"]
        if repo_path.exists():
            shutil.rmtree(repo_path, ignore_errors=True)

    # Eliminar proyectos generados
    project_path = PROJECTS_DIR / session_id
    if project_path.exists():
        shutil.rmtree(project_path, ignore_errors=True)

    # Eliminar entorno virtual de la sesión
    venv_path = VENVS_DIR / session_id
    if venv_path.exists():
        shutil.rmtree(venv_path, ignore_errors=True)

    return True

def cleanup_expired_sessions():
    now = datetime.utcnow()
    expired = [sid for sid, session in sessions.items() if now > session["expires_at"]]
    for sid in expired:
        delete_session(sid)

# =============================================================================
# DETECCIÓN DE AGENTES
# =============================================================================
def detect_agents(repo_path: Path) -> List[Dict[str, Any]]:
    agents = []
    agent_files = ["agent.json", "agent.py", "main.py"]

    for root, dirs, files in os.walk(repo_path):
        # Excluir carpetas innecesarias
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.git']]

        for file in files:
            if file in agent_files:
                file_path = Path(root) / file
                relative_path = file_path.relative_to(repo_path)

                agent_info = {
                    "id": str(uuid.uuid4())[:8],
                    "name": file_path.parent.name if file_path.parent != repo_path else "root",
                    "description": "Agent detected in repository",
                    "icon": "🤖",
                    "path": str(relative_path),
                    "full_path": str(file_path.resolve()),
                    "type": file
                }

                if file == "agent.json":
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                            agent_info["name"] = config.get("name", agent_info["name"])
                            agent_info["description"] = config.get("description", agent_info["description"])
                            agent_info["icon"] = config.get("icon", "🤖")
                    except Exception:
                        pass

                readme_path = file_path.parent / "README.md"
                if readme_path.exists():
                    try:
                        with open(readme_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            agent_info["description"] = content[:200] + "..." if len(content) > 200 else content
                    except Exception:
                        pass

                agents.append(agent_info)

    return agents

# =============================================================================
# MANEJO DE ENTORNOS VIRTUALES Y DEPENDENCIAS
# =============================================================================
def get_venv_python(session_id: str) -> Path:
    """Devuelve la ruta al ejecutable de Python del entorno virtual de la sesión.
    Si el entorno no existe, lo crea."""
    venv_dir = VENVS_DIR / session_id
    if not venv_dir.exists():
        subprocess.run(["python", "-m", "venv", str(venv_dir)], check=True)
    # Ruta al ejecutable de Python dentro del venv
    if os.name == "nt":  # Windows
        return venv_dir / "Scripts" / "python.exe"
    else:  # Linux/Mac
        return venv_dir / "bin" / "python"

def install_agent_dependencies(agent_dir: Path, repo_root: Path, session_id: str):
    """
    Instala dependencias del agente en el entorno virtual de la sesión.
    Si encuentra 'langchain' sin versión fija, la fuerza a 0.1.0.
    """
    venv_python = get_venv_python(session_id)

    # Buscar requirements.txt
    requirements_found = None
    possible_paths = [
        agent_dir / "requirements.txt",
        repo_root / "requirements.txt"
    ]
    for path in possible_paths:
        if path.exists():
            requirements_found = path
            break

    if requirements_found:
        print(f"📦 Procesando dependencias desde {requirements_found}")
        # Leer el contenido del archivo
        with open(requirements_found, 'r') as f:
            lines = f.readlines()

        # Modificar las líneas que empiezan con 'langchain' para fijar la versión 0.1.0
        new_lines = []
        modified = False
        for line in lines:
            stripped = line.strip()
            # Si la línea es langchain sin versión fija (>= o solo el nombre)
            if stripped.startswith('langchain') and ('>=' in stripped or '==' not in stripped):
                new_lines.append('langchain==0.1.0\n')
                modified = True
                print("   🔧 Forzando langchain==0.1.0 para compatibilidad")
            else:
                new_lines.append(line)

        # Si no se modificó ninguna línea de langchain, pero existe langchain, igual forzamos versión?
        # (opcional) Podríamos siempre forzar si aparece langchain sin ==
        # Por ahora solo si cumple condición anterior.

        # Escribir un archivo temporal en el directorio de la sesión
        temp_req = VENVS_DIR / session_id / "requirements.txt"
        temp_req.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_req, 'w') as f:
            f.writelines(new_lines)

        # Instalar desde el archivo temporal
        result = subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-r", str(temp_req)],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode != 0:
            print(f"⚠️ Error instalando dependencias: {result.stderr}")
        else:
            print("✅ Dependencias instaladas correctamente")
    else:
        # Fallback: instalar langchain==0.1.0 por si acaso
        print("📦 No se encontró requirements.txt, instalando langchain==0.1.0")
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "langchain==0.1.0"],
            capture_output=True,
            text=True,
            timeout=60
        )

# =============================================================================
# TAREA DE LIMPIEZA EN SEGUNDO PLANO
# =============================================================================
async def cleanup_task():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_MINUTES * 60)
        cleanup_expired_sessions()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Limpiar sesiones expiradas al arrancar
    cleanup_expired_sessions()
    task = asyncio.create_task(cleanup_task())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

# =============================================================================
# APLICACIÓN FASTAPI
# =============================================================================
app = FastAPI(
    title="GitAgent-Clon API",
    description="Backend para clonar repositorios y ejecutar agentes de IA locales",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# ENDPOINTS
# =============================================================================
@app.post("/api/clone")
async def clone_repository(request: CloneRequest):
    session_id = create_session()
    session = sessions[session_id]

    try:
        session_repo_dir = REPOS_DIR / session_id
        session_repo_dir.mkdir(parents=True, exist_ok=True)

        clone_result = subprocess.run(
            ["git", "clone", "--depth", "1", request.repoUrl, "."],
            cwd=session_repo_dir,
            capture_output=True,
            text=True,
            timeout=120
        )

        if clone_result.returncode != 0:
            delete_session(session_id)
            raise HTTPException(status_code=400, detail=f"Failed to clone: {clone_result.stderr}")

        session["repo_path"] = session_id
        agents = detect_agents(session_repo_dir)
        session["agents"] = agents

        project_dir = PROJECTS_DIR / session_id
        project_dir.mkdir(parents=True, exist_ok=True)

        return {"sessionId": session_id, "agents": agents}

    except subprocess.TimeoutExpired:
        delete_session(session_id)
        raise HTTPException(status_code=408, detail="Clone timed out")
    except Exception as e:
        delete_session(session_id)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agents/{session_id}")
async def get_agents(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"sessionId": session_id, "agents": session["agents"]}

@app.post("/api/select-agent/{session_id}/{agent_id}")
async def select_agent(session_id: str, agent_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    agent = next((a for a in session["agents"] if a["id"] == agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    session["selected_agent"] = agent
    return {"sessionId": session_id, "selectedAgent": agent}

@app.post("/api/chat")
async def chat(request: ChatRequest):
    session = get_session(request.sessionId)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    agent = next((a for a in session["agents"] if a["id"] == request.agentId), None)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Preparar entorno
    env = os.environ.copy()
    env["OPENAGENT_INPUT"] = request.message
    env["OPENAGENT_SESSION_ID"] = request.sessionId
    env["OPENAGENT_PROJECT_DIR"] = str(PROJECTS_DIR / request.sessionId)

    agent_path = Path(agent["full_path"])
    working_dir = agent_path.parent
    repo_root = REPOS_DIR / session["repo_path"]

    # Instalar dependencias en el entorno virtual de la sesión
    install_agent_dependencies(working_dir, repo_root, request.sessionId)

    # Obtener el Python del entorno virtual
    venv_python = get_venv_python(request.sessionId)

    try:
        if agent["type"] == "agent.json":
            with open(agent_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            command = config.get("command", ["python", "agent.py"])
            if isinstance(command, str):
                command = command.split()
            # Asegurar que se use el Python del venv
            command[0] = str(venv_python) if command[0] == "python" else command[0]
            result = subprocess.run(command, cwd=working_dir, capture_output=True, text=True, env=env, timeout=30)
        elif agent["type"] in ["agent.py", "main.py"]:
            result = subprocess.run(
                [str(venv_python), str(agent_path)],
                cwd=working_dir,
                capture_output=True,
                text=True,
                env=env,
                timeout=30
            )
        else:
            raise HTTPException(status_code=400, detail="Unknown agent type")

        output = result.stdout if result.returncode == 0 else result.stderr

        project_dir = PROJECTS_DIR / request.sessionId
        generated_files = []
        if project_dir.exists():
            for item in project_dir.iterdir():
                if item.is_file():
                    generated_files.append(item.name)

        session["files_generated"] = generated_files

        return {
            "response": output,
            "files": generated_files,
            "error": result.stderr if result.returncode != 0 else None
        }

    except subprocess.TimeoutExpired:
        return {"response": "", "files": [], "error": "Agent timed out (30s limit)"}
    except Exception as e:
        return {"response": "", "files": [], "error": str(e)}

@app.get("/api/files/{session_id}")
async def get_files(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    project_dir = PROJECTS_DIR / session_id
    files = []
    if project_dir.exists():
        for item in project_dir.rglob("*"):
            if item.is_file():
                try:
                    with open(item, 'r', encoding='utf-8') as f:
                        content = f.read()
                    files.append({
                        "name": item.name,
                        "path": str(item.relative_to(project_dir)),
                        "content": content,
                        "size": item.stat().st_size
                    })
                except Exception:
                    pass
    return {"sessionId": session_id, "files": files}

@app.get("/api/download/{session_id}")
async def download_files(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    project_dir = PROJECTS_DIR / session_id
    if not project_dir.exists() or not any(project_dir.iterdir()):
        raise HTTPException(status_code=404, detail="No files")

    zip_path = DATA_DIR / f"{session_id}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for item in project_dir.rglob("*"):
            if item.is_file():
                zipf.write(item, str(item.relative_to(project_dir)))

    return FileResponse(zip_path, media_type='application/zip', filename=f"gitagent-{session_id}.zip")

@app.delete("/api/session/{session_id}")
async def delete_session_endpoint(session_id: str):
    if delete_session(session_id):
        return {"message": "Session deleted"}
    raise HTTPException(status_code=404, detail="Session not found")

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "active_sessions": len(sessions),
        "timestamp": datetime.utcnow().isoformat()
    }

# =============================================================================
# SERVIDOR DE ARCHIVOS ESTÁTICOS (FRONTEND)
# =============================================================================
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")

# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
