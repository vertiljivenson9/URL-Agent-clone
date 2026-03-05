"""
GitAgent-Clon Backend - FastAPI Application
Versión Universal: Detecta y ejecuta cualquier agente de IA en cualquier repositorio.
"""

import os
import json
import shutil
import subprocess
import uuid
import zipfile
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
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
VENVS_DIR = DATA_DIR / "venvs"
SESSION_TIMEOUT_HOURS = 6
CLEANUP_INTERVAL_MINUTES = 30

# Crear directorios necesarios
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
        "files_generated": [],
        "process": None  # Para procesos en segundo plano (servidores)
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

    # Matar proceso en segundo plano si existe
    if session.get("process"):
        try:
            session["process"].terminate()
        except:
            pass

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
# DETECCIÓN INTELIGENTE DE AGENTES
# =============================================================================
def is_likely_entry_point(file_path: Path) -> bool:
    """Determina si un archivo .py es probablemente un punto de entrada."""
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        # Buscar patrones comunes de punto de entrada
        patterns = [
            r'if\s+__name__\s*==\s*["\']__main__["\']\s*:',
            r'app\s*=\s*FastAPI\(',
            r'uvicorn\.run\(',
            r'flask\.Flask\(',
            r'def\s+main\s*\(',
            r'cli\.main\(',
            r'typer\.run\(',
            r'if\s+__name__\s*==\s*["\']__main__["\']\s*:'
        ]
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    except:
        return False

def detect_agents(repo_path: Path) -> List[Dict[str, Any]]:
    """Detecta posibles agentes en el repositorio usando múltiples estrategias."""
    agents = []
    # Lista de nombres de archivo comunes para puntos de entrada
    common_entry_names = [
        "agent.py", "main.py", "app.py", "run.py", "server.py", 
        "cli.py", "launch.py", "start.py", "bot.py", "chat.py",
        "inference.py", "predict.py", "train.py", "serve.py"
    ]
    
    # Primero, buscar archivos con nombres comunes
    for root, dirs, files in os.walk(repo_path):
        # Excluir carpetas innecesarias
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.git', 'env']]
        
        for file in files:
            file_path = Path(root) / file
            relative_path = file_path.relative_to(repo_path)
            
            # Si el nombre coincide con la lista común, es candidato
            if file in common_entry_names:
                agent_info = {
                    "id": str(uuid.uuid4())[:8],
                    "name": f"{file_path.parent.name}/{file}" if file_path.parent != repo_path else file,
                    "description": "Posible agente detectado por nombre de archivo",
                    "icon": "🤖",
                    "path": str(relative_path),
                    "full_path": str(file_path.resolve()),
                    "type": file,
                    "confidence": "high"
                }
                
                # Leer README.md cercano para descripción
                readme_path = file_path.parent / "README.md"
                if readme_path.exists():
                    try:
                        content = readme_path.read_text(encoding='utf-8', errors='ignore')
                        agent_info["description"] = content[:200] + "..." if len(content) > 200 else content
                    except:
                        pass
                
                agents.append(agent_info)
            
            # Si es un archivo .py, analizar si es punto de entrada
            elif file.endswith('.py') and is_likely_entry_point(file_path):
                agent_info = {
                    "id": str(uuid.uuid4())[:8],
                    "name": f"{file_path.parent.name}/{file}" if file_path.parent != repo_path else file,
                    "description": "Posible agente detectado por análisis de código",
                    "icon": "🔍",
                    "path": str(relative_path),
                    "full_path": str(file_path.resolve()),
                    "type": file,
                    "confidence": "medium"
                }
                agents.append(agent_info)
    
    # Si no se encontró nada, buscar cualquier archivo .py que no esté en carpetas obvias
    if not agents:
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.git', 'env', 'tests', 'docs']]
            py_files = [f for f in files if f.endswith('.py') and f not in ['__init__.py', 'setup.py', 'conf.py']]
            if py_files:
                # Tomar el primer archivo .py como candidato
                file = py_files[0]
                file_path = Path(root) / file
                agent_info = {
                    "id": str(uuid.uuid4())[:8],
                    "name": f"{file_path.parent.name}/{file}" if file_path.parent != repo_path else file,
                    "description": "Posible agente (archivo .py encontrado)",
                    "icon": "📄",
                    "path": str(file_path.relative_to(repo_path)),
                    "full_path": str(file_path.resolve()),
                    "type": file,
                    "confidence": "low"
                }
                agents.append(agent_info)
                break  # Solo uno para no saturar
    
    return agents

# =============================================================================
# MANEJO DE ENTORNOS VIRTUALES Y DEPENDENCIAS
# =============================================================================
def get_venv_python(session_id: str) -> Path:
    """Devuelve la ruta al ejecutable de Python del entorno virtual de la sesión."""
    venv_dir = VENVS_DIR / session_id
    if not venv_dir.exists():
        subprocess.run(["python", "-m", "venv", str(venv_dir)], check=True)
    if os.name == "nt":  # Windows
        return venv_dir / "Scripts" / "python.exe"
    else:  # Linux/Mac
        return venv_dir / "bin" / "python"

def find_requirements(repo_root: Path) -> Optional[Path]:
    """Busca un archivo de requisitos en el repositorio."""
    # Buscar requirements.txt en la raíz o en subcarpetas comunes
    possible_paths = [
        repo_root / "requirements.txt",
        repo_root / "requirements" / "requirements.txt",
        repo_root / "requirements" / "base.txt",
        repo_root / "setup.py",  # para proyectos con setup.py
        repo_root / "pyproject.toml",  # para proyectos con poetry
    ]
    for path in possible_paths:
        if path.exists():
            return path
    
    # Búsqueda recursiva (limitada a profundidad 2 para no ser muy lento)
    for root, dirs, files in os.walk(repo_root):
        if root.count(os.sep) - len(repo_root.parts) > 2:
            continue
        if "requirements.txt" in files:
            return Path(root) / "requirements.txt"
    return None

def install_agent_dependencies(repo_root: Path, session_id: str):
    """
    Instala las dependencias del agente en el entorno virtual de la sesión.
    Soporta requirements.txt, setup.py y pyproject.toml.
    """
    venv_python = get_venv_python(session_id)
    req_file = find_requirements(repo_root)
    
    if req_file:
        print(f"📦 Instalando dependencias desde {req_file}")
        try:
            if req_file.name == "requirements.txt":
                # Leer y modificar versiones problemáticas (como langchain)
                with open(req_file, 'r') as f:
                    lines = f.readlines()
                
                new_lines = []
                for line in lines:
                    stripped = line.strip()
                    # Forzar versiones conocidas para paquetes problemáticos
                    if stripped.startswith('langchain') and ('>=' in stripped or '==' not in stripped):
                        new_lines.append('langchain==0.1.0\n')
                        print("   🔧 Forzando langchain==0.1.0 para compatibilidad")
                    else:
                        new_lines.append(line)
                
                # Guardar temporalmente en el directorio del venv
                temp_req = VENVS_DIR / session_id / "requirements.txt"
                temp_req.parent.mkdir(parents=True, exist_ok=True)
                with open(temp_req, 'w') as f:
                    f.writelines(new_lines)
                
                subprocess.run(
                    [str(venv_python), "-m", "pip", "install", "-r", str(temp_req)],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minutos para instalar
                )
            elif req_file.name == "setup.py":
                # Instalar en modo editable
                subprocess.run(
                    [str(venv_python), "-m", "pip", "install", "-e", str(req_file.parent)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            elif req_file.name == "pyproject.toml":
                # Intentar con poetry si está disponible
                try:
                    subprocess.run(
                        ["poetry", "install"],
                        cwd=req_file.parent,
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                except:
                    # Fallback a pip
                    subprocess.run(
                        [str(venv_python), "-m", "pip", "install", "."],
                        cwd=req_file.parent,
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
            print("✅ Dependencias instaladas correctamente")
        except Exception as e:
            print(f"⚠️ Error instalando dependencias: {e}")
    else:
        print("📦 No se encontró archivo de requisitos, instalando solo langchain por defecto")
        try:
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "langchain==0.1.0"],
                capture_output=True,
                text=True,
                timeout=60
            )
        except:
            pass

# =============================================================================
# EJECUCIÓN DE AGENTES
# =============================================================================
async def run_agent_process(venv_python: Path, agent_path: Path, working_dir: Path, env: dict, session_id: str):
    """Ejecuta el agente y maneja su salida."""
    cmd = [str(venv_python), str(agent_path)]
    
    # Detectar si es un servidor web (FastAPI, Flask) para ejecutarlo en segundo plano
    try:
        content = agent_path.read_text(encoding='utf-8', errors='ignore')
        is_web_server = any(x in content for x in ['FastAPI', 'Flask', 'uvicorn.run', 'app.run'])
    except:
        is_web_server = False
    
    if is_web_server:
        # Ejecutar en segundo plano
        process = subprocess.Popen(
            cmd,
            cwd=working_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        # Guardar el proceso en la sesión para poder matarlo después
        session = sessions.get(session_id)
        if session:
            session["process"] = process
        # Devolver mensaje indicando que el servidor inició
        return {"response": "Servidor web iniciado en segundo plano. Revisa los logs para más detalles.", "files": []}
    else:
        # Ejecución normal con timeout
        try:
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                env=env,
                timeout=60  # 60 segundos para ejecución normal
            )
            return {
                "response": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
                "files": []
            }
        except subprocess.TimeoutExpired:
            return {"response": "", "error": "El agente tardó demasiado (60s)", "files": []}

# =============================================================================
# TAREA DE LIMPIEZA EN SEGUNDO PLANO
# =============================================================================
async def cleanup_task():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_MINUTES * 60)
        cleanup_expired_sessions()

@asynccontextmanager
async def lifespan(app: FastAPI):
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
    description="Backend universal para clonar repositorios y ejecutar agentes de IA",
    version="3.0.0",
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
    install_agent_dependencies(repo_root, request.sessionId)

    # Obtener el Python del entorno virtual
    venv_python = get_venv_python(request.sessionId)

    # Ejecutar el agente
    result = await run_agent_process(venv_python, agent_path, working_dir, env, request.sessionId)

    # Buscar archivos generados en PROJECTS_DIR
    project_dir = PROJECTS_DIR / request.sessionId
    generated_files = []
    if project_dir.exists():
        for item in project_dir.iterdir():
            if item.is_file():
                generated_files.append(item.name)

    session["files_generated"] = generated_files

    return {
        "response": result.get("response", ""),
        "files": generated_files,
        "error": result.get("error")
    }

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
