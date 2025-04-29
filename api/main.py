import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()


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
