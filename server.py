#!/usr/bin/env python3
"""
LLM & RAG Quiz — Live Answer Collection Server
Arş. Gör. Merve DEDE | Istanbul Beykent University

Run:
    pip install fastapi uvicorn websockets
    python server.py

Students  → http://<your-ip>:8000/
Presenter → http://localhost:8000/presenter
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

HERE = Path(__file__).parent

app = FastAPI(title="LLM RAG Quiz Live")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── In-memory state ──────────────────────────────────────────────────────────
N_QUESTIONS = 5
OPTION_KEYS  = ["A", "B", "C", "D"]

# Per-question vote counts
votes: list[dict[str, int]] = [
    {"A": 0, "B": 0, "C": 0, "D": 0, "timeout": 0, "total": 0}
    for _ in range(N_QUESTIONS)
]

# Student registry: {student_id: {q_index: choice_index | "timeout"}}
students: dict[str, dict[int, Any]] = {}

# Presenter WebSocket connections
presenter_connections: list[WebSocket] = []

# Session log with timestamps
event_log: list[dict] = []

# ── Helpers ──────────────────────────────────────────────────────────────────
def state_snapshot() -> dict:
    return {
        "votes": votes,
        "student_count": len(students),
        "event_log": event_log[-20:],  # last 20 events
    }

async def broadcast_to_presenters(data: dict) -> None:
    dead = []
    msg = json.dumps(data)
    for ws in presenter_connections:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        presenter_connections.remove(ws)

# ── Routes ───────────────────────────────────────────────────────────────────
@app.get("/")
async def student_page():
    return FileResponse(HERE / "student.html")

@app.get("/presenter")
async def presenter_page():
    return FileResponse(HERE / "presenter.html")

@app.post("/answer")
async def receive_answer(payload: dict):
    """
    Expected payload:
    {
      "student_id": "Ali",
      "question_index": 2,       // 0-based
      "choice_index": 1,         // 0-based (A=0,B=1,C=2,D=3) or -1 for timeout
      "timed_out": false
    }
    """
    sid   = str(payload.get("student_id", "anon")).strip() or "anon"
    qidx  = int(payload.get("question_index", 0))
    cidx  = payload.get("choice_index", -1)
    tout  = bool(payload.get("timed_out", False))

    if qidx < 0 or qidx >= N_QUESTIONS:
        return {"status": "ignored", "reason": "invalid question_index"}

    # Register student
    if sid not in students:
        students[sid] = {}

    # Deduplicate: ignore repeat submissions for same question
    if qidx in students[sid]:
        return {"status": "duplicate"}

    students[sid][qidx] = "timeout" if tout else cidx

    # Update vote counts
    votes[qidx]["total"] += 1
    if tout:
        votes[qidx]["timeout"] += 1
    elif 0 <= cidx < 4:
        votes[qidx][OPTION_KEYS[cidx]] += 1

    # Log event
    event_log.append({
        "t": time.strftime("%H:%M:%S"),
        "student": sid,
        "q": qidx + 1,
        "choice": "Süre Doldu" if tout else OPTION_KEYS[cidx] if 0 <= cidx < 4 else "?",
    })

    await broadcast_to_presenters({"type": "update", **state_snapshot()})
    return {"status": "ok"}

@app.post("/reset")
async def reset_state():
    global votes, students, event_log
    votes = [
        {"A": 0, "B": 0, "C": 0, "D": 0, "timeout": 0, "total": 0}
        for _ in range(N_QUESTIONS)
    ]
    students = {}
    event_log = []
    await broadcast_to_presenters({"type": "reset", **state_snapshot()})
    return {"status": "reset"}

@app.get("/state")
async def get_state():
    return state_snapshot()

@app.websocket("/ws/presenter")
async def presenter_ws(ws: WebSocket):
    await ws.accept()
    presenter_connections.append(ws)
    # Send current state immediately on connect
    await ws.send_text(json.dumps({"type": "init", **state_snapshot()}))
    try:
        while True:
            await ws.receive_text()   # keep-alive ping from client
    except WebSocketDisconnect:
        if ws in presenter_connections:
            presenter_connections.remove(ws)

if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"

    print("\n" + "="*55)
    print("  LLM & RAG Quiz — Live Server")
    print("="*55)
    print(f"  Öğrenci linki  → http://{local_ip}:8000/")
    print(f"  Presenter      → http://localhost:8000/presenter")
    print(f"  Reset          → POST http://localhost:8000/reset")
    print("="*55 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
