from fastapi import FastAPI
from fastapi.responses import FileResponse

import field_mappings as m
from fetch_and_fuse_records import fetch_and_fuse

app = FastAPI()


@app.get("/api/fuse/{taxid}")
def fuse_taxid(taxid: int):
    fused = fetch_and_fuse(taxid, m.test1)
    return list(fused.values())


@app.get("/")
def index():
    return FileResponse("index.html")


@app.get("/app.js")
def js():
    return FileResponse("app.js")

# run:  uvicorn server:app --reload     then open http://127.0.0.1:8000
