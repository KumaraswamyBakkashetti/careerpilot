// @vitest-environment node
import { expect, it } from "vitest";
import { ApiClient } from "./client";
import { getHealth } from "./health";
import { getRoleSkills, getRoles } from "./knowledge";
import {
  authenticate,
  decideEvidence,
  getEvidence,
  runGap,
  updateProfile,
  uploadResume,
} from "./student";

function syntheticPdf(): ArrayBuffer {
  const lines = [
    "SKILLS",
    "Python, SQL, MysteryTool",
    "PROJECTS",
    "Built REST APIs with Python",
  ];
  const commands = ["BT /F1 12 Tf 72 720 Td"];
  lines.forEach((line, index) =>
    commands.push(`${index === 0 ? "" : "0 -18 Td "}(${line}) Tj`),
  );
  commands.push("ET");
  const stream = commands.join("\n");
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let content = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((value, index) => {
    offsets.push(content.length);
    content += `${index + 1} 0 obj\n${value}\nendobj\n`;
  });
  const xref = content.length;
  content += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  offsets.forEach((offset) => {
    content += `${String(offset).padStart(10, "0")} 00000 n \n`;
  });
  content += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  const bytes = new TextEncoder().encode(content);
  return bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength,
  ) as ArrayBuffer;
}

it.skipIf(process.env.CP_RUN_FRONTEND_INTEGRATION !== "1")(
  "real frontend client → Vite proxy → FastAPI → both databases",
  async () => {
    const health = await getHealth(
      undefined,
      new ApiClient("http://127.0.0.1:5173"),
    );
    expect(health.status).toBe("ready");
    expect(health.dependencies).toEqual({ mongodb: "up", neo4j: "up" });
    expect(health.requestId).toMatch(/^[A-Za-z0-9_-]{1,64}$/);
  },
);

it.skipIf(process.env.CP_RUN_FRONTEND_INTEGRATION !== "1")(
  "real frontend client performs the private resume and cross-store gap flow",
  async () => {
    const client = new ApiClient("http://127.0.0.1:5173", 20_000);
    const identity = `${Date.now()}-${crypto.randomUUID()}@example.test`;
    const token = await authenticate(
      "register",
      {
        email: identity,
        password: "synthetic-frontend-test-password",
        display_name: "Synthetic Frontend Student",
      },
      client,
    );
    const uploaded = await uploadResume(
      token,
      new File([syntheticPdf()], "synthetic-frontend.pdf", {
        type: "application/pdf",
      }),
      client,
    );
    expect(uploaded.status).toBe("AWAITING_CONFIRMATION");
    const evidence = await getEvidence(token, uploaded.resume_id, client);
    expect(evidence.some((item) => item.skill_id === "skill_python")).toBe(
      true,
    );
    expect(evidence.some((item) => item.skill_id === null)).toBe(true);
    for (const item of evidence.filter(
      (value) => value.skill_id === "skill_python",
    )) {
      await decideEvidence(
        token,
        item.evidence_id,
        "CONFIRM",
        undefined,
        client,
      );
    }
    await updateProfile(
      token,
      { target_role_id: "role_backend_developer" },
      client,
    );
    const gap = await runGap(token, client);
    expect(gap.knowledge_dataset_version).toBe("careerpilot-knowledge-v1");
    expect(
      gap.items.find((item) => item.skill_id === "skill_python")?.status,
    ).toBe("SUPPORTED");
    expect(
      gap.items.find((item) => item.skill_id === "skill_sql")?.status,
    ).toBe("PARTIALLY_SUPPORTED");
    expect(gap.items.some((item) => item.status === "UNVERIFIED")).toBe(true);
  },
  30_000,
);

it.skipIf(process.env.CP_RUN_FRONTEND_INTEGRATION !== "1")(
  "real frontend client → Vite proxy → FastAPI → Neo4j knowledge",
  async () => {
    const client = new ApiClient("http://127.0.0.1:5173");
    const roles = await getRoles(undefined, client);
    expect(roles.items).toHaveLength(5);
    const backend = roles.items.find(
      (role) => role.id === "role_backend_developer",
    );
    expect(backend?.name).toBe("Backend Developer");
    const skills = await getRoleSkills(backend!.id, undefined, client);
    expect(skills.items).toHaveLength(10);
    const python = skills.items.find(
      (item) => item.entity.id === "skill_python",
    );
    expect(python?.evidence.assertion.importance).toBe("CORE");
    expect(python?.evidence.provenance[0]?.source.title).toBe(
      "CareerPilot v1 curated learning profiles",
    );
  },
);
