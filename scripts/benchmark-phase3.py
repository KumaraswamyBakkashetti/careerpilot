"""Measure the local Phase 3 HTTP path against disposable infrastructure."""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
from uuid import uuid4


def synthetic_pdf(run: int) -> bytes:
    lines = ["SKILLS", "Python, SQL, MysteryTool", "PROJECTS", f"Built REST APIs {run}"]
    commands = ["BT /F1 12 Tf 72 720 Td"]
    for index, line in enumerate(lines):
        commands.append(("" if index == 0 else "0 -18 Td ") + f"({line}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, value in enumerate(objects, 1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode() + value + b"\nendobj\n")
    xref = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        content.extend(f"{offset:010d} 00000 n \n".encode())
    content.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(content)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(len(ordered) * fraction + 0.999) - 1))]


class Client:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.token = ""

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        content_type: str | None = "application/json",
    ) -> Any:
        headers = {"Accept": "application/json", "X-Request-ID": f"benchmark-{uuid4().hex}"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if body is not None and content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(self.base + path, body, headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{method} {path} returned {exc.code}: {exc.read().decode()}") from exc
        return json.loads(payload) if payload else None

    def json(self, method: str, path: str, value: object | None = None) -> Any:
        body = json.dumps(value).encode() if value is not None else None
        return self.request(method, path, body)

    def upload(self, run: int) -> Any:
        boundary = f"CareerPilot{uuid4().hex}"
        file = synthetic_pdf(run)
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"benchmark-{run}.pdf\"\r\nContent-Type: application/pdf\r\n\r\n"
        ).encode() + file + f"\r\n--{boundary}--\r\n".encode()
        return self.request(
            "POST",
            "/api/v1/student/resumes",
            body,
            f"multipart/form-data; boundary={boundary}",
        )


def timed(samples: dict[str, list[float]], name: str, operation: Callable[[], Any]) -> Any:
    start = time.perf_counter()
    value = operation()
    samples.setdefault(name, []).append((time.perf_counter() - start) * 1000)
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8001")
    parser.add_argument("--iterations", type=int, default=7)
    args = parser.parse_args()
    if not 3 <= args.iterations <= 30:
        raise SystemExit("iterations must be between 3 and 30")
    client = Client(args.base)
    samples: dict[str, list[float]] = {}
    identity = f"benchmark-{uuid4().hex}@example.test"
    auth = client.json(
        "POST",
        "/api/v1/auth/register",
        {
            "email": identity,
            "password": "synthetic-benchmark-password",
            "display_name": "Synthetic Benchmark",
        },
    )
    client.token = auth["access_token"]
    resumes = []
    for run in range(args.iterations):
        resumes.append(timed(samples, "pdf_upload_extract_normalize", lambda run=run: client.upload(run)))
    active_id = resumes[-1]["resume_id"]
    evidence = None
    for _ in range(args.iterations):
        evidence = timed(
            samples,
            "evidence_retrieval",
            lambda: client.json("GET", f"/api/v1/student/resumes/{active_id}/evidence"),
        )
    for _ in range(args.iterations):
        timed(
            samples,
            "role_requirement_retrieval",
            lambda: client.json(
                "GET", "/api/v1/knowledge/roles/role_backend_developer/skills"
            ),
        )
    for item in evidence:
        if item["skill_id"] == "skill_python":
            client.json(
                "PUT",
                f"/api/v1/student/evidence/{item['evidence_id']}",
                {"action": "CONFIRM"},
            )
    client.json(
        "PUT", "/api/v1/student/profile", {"target_role_id": "role_backend_developer"}
    )
    gaps = []
    for _ in range(args.iterations):
        gaps.append(timed(samples, "gap_analysis", lambda: client.json("POST", "/api/v1/student/gap-analyses")))
    result = {
        "environment": "local isolated Docker dependencies; synchronous FastAPI pipeline",
        "iterations": args.iterations,
        "milliseconds": {
            name: {
                "median": round(statistics.median(values), 2),
                "p95": round(percentile(values, 0.95), 2),
            }
            for name, values in samples.items()
        },
        "assertions": {
            "resume_status": resumes[-1]["status"],
            "gap_rule_version": gaps[-1]["rule_version"],
            "knowledge_dataset_version": gaps[-1]["knowledge_dataset_version"],
        },
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
