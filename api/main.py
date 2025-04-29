import os
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

app = FastAPI()

# In-memory storage for todos
todos_db = []
next_id = 1

class Todo(BaseModel):
    id: int
    text: str
    done: bool

class CreateTodo(BaseModel):
    text: str = Field(..., min_length=1)


@app.get("/api/todos", response_model=List[Todo])
async def get_todos():
    return todos_db

@app.post("/api/todos", response_model=Todo)
async def create_todo(todo_in: CreateTodo):
    global next_id
    new_todo = Todo(id=next_id, text=todo_in.text, done=False)
    todos_db.append(new_todo)
    next_id += 1
    return new_todo

@app.delete("/api/todos/{todo_id}", status_code=204)
async def delete_todo(todo_id: int):
    global todos_db
    initial_len = len(todos_db)
    todos_db = [todo for todo in todos_db if todo.id != todo_id]
    if len(todos_db) == initial_len:
        raise HTTPException(status_code=404, detail="Todo not found")
    return None # No content response

@app.put("/api/todos/{todo_id}/toggle", response_model=Todo)
async def toggle_todo_done(todo_id: int):
    for todo in todos_db:
        if todo.id == todo_id:
            todo.done = not todo.done
            return todo
    raise HTTPException(status_code=404, detail="Todo not found")


@app.get("/api/hello")
async def hello():
    return {"message": "Hello from FastAPI!"}


static_files_path = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
app.mount(
    "/assets",
    StaticFiles(directory=os.path.join(static_files_path, "assets")),
    name="assets",
)


@app.get("/{full_path:path}")
async def serve_vue_app(full_path: str):
    index_path = os.path.join(static_files_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)

    return {"error": "index.html not found"}


@app.get("/")
async def serve_index():
    index_path = os.path.join(static_files_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "index.html not found"}
