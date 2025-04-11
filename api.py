from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import requests
import os
import subprocess
import json


app = FastAPI()

GITHUB_REPO_URI = os.environ.get("GITHUB_REPO_URI")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH")
NOMAD_ADDR = os.environ.get("NOMAD_ADDR")
NOMAD_TOKEN = os.environ.get("NOMAD_ACL_TOKEN")


class Deployment(BaseModel):
    job_id: str
    file_path: str
    file_name: str


def download_file(deployment: Deployment) -> str:
    github_file_url = f"{GITHUB_REPO_URI}/{GITHUB_BRANCH}/{deployment.file_path}/{deployment.file_name}"
    response = requests.get(github_file_url, allow_redirects=True)
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="File not found on GitHub")

    os.makedirs("./jobs", exist_ok=True)
    local_path = f"./jobs/{deployment.file_name}"
    with open(local_path, "wb") as f:
        f.write(response.content)

    return local_path


def parse_job(local_path: str) -> str:
    parsed_path = "./jobs/parsed-job.json"
    result = subprocess.run(
        ["nomad", "job", "run", "-output", local_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500, detail=f"Nomad validation error: {result.stderr.decode()}"
        )

    with open(parsed_path, "w") as f:
        f.write(result.stdout.decode())

    return parsed_path


def update_nomad_job_meta(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        job = json.load(f)

    if "Meta" not in job:
        job["Job"]["Meta"] = {}

    job["Job"]["Meta"]["updated_at"] = datetime.utcnow().isoformat() + "Z"

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2)


def deploy_to_nomad(parsed_file_path: str):
    with open(parsed_file_path, "rb") as f:
        response = requests.post(
            f"{NOMAD_ADDR}/v1/jobs",
            headers={
                "Content-Type": "application/json",
                "X-Nomad-Token": NOMAD_TOKEN or "",
            },
            data=f,
        )

    print(response.json())
    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Nomad deploy failed: {response.text}",
        )


def remove_file(path: str):
    if os.path.exists(path):
        os.remove(path)


@app.get("/health")
async def get_health():
    return {"status": "ok"}


@app.post("/deployment")
async def deploy_app(deployment: Deployment):
    job_file = download_file(deployment)
    try:
        parsed_file = parse_job(job_file)
        update_nomad_job_meta(parsed_file)
        deploy_to_nomad(parsed_file)
    finally:
        remove_file(job_file)
        remove_file("./jobs/parsed-job.json")

    return {"status": "success", "job": deployment.file_name}
