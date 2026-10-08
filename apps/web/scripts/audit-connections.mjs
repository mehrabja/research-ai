#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, "..");
const srcRoot = path.join(webRoot, "src");
const clientPath = path.join(srcRoot, "lib", "api", "client.ts");

const failures = [];

const walk = (dir) => {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (["node_modules", ".next", "dist"].includes(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full);
    else if (/\.(ts|tsx)$/.test(entry.name)) {
      const source = fs.readFileSync(full, "utf8");
      const relative = path.relative(webRoot, full).replaceAll("\\", "/");
      if (relative !== "src/lib/api/client.ts" && /\bfetch\s*\(/.test(source)) {
        failures.push(`${relative}: direct fetch() outside the central API client`);
      }
      if (/https?:\/\/localhost:\d+|https?:\/\/127\.0\.0\.1:\d+/.test(source)) {
        failures.push(`${relative}: hard-coded local backend URL`);
      }
    }
  }
};

walk(srcRoot);

const client = fs.readFileSync(clientPath, "utf8");

if (!/async function rawRequest<T>/.test(client)) {
  failures.push("src/lib/api/client.ts: central rawRequest() is missing");
}
if (!/fetch\("\/api\/backend\/"/.test(client)) {
  failures.push("src/lib/api/client.ts: backend requests are not routed through /api/backend");
}
if (!/fetch\("\/api\/auth\/refresh"/.test(client)) {
  failures.push("src/lib/api/client.ts: refresh flow is missing");
}
if ((client.match(/request<[^>]+>\(/g) ?? []).length < 10) {
  failures.push("src/lib/api/client.ts: unexpectedly small typed API surface");
}

if (failures.length) {
  console.error("Frontend API connection audit failed.");
  for (const failure of failures) console.error(" - " + failure);
  process.exit(1);
}

console.log("Frontend API connection audit passed.");
console.log(" - central API client: OK");
console.log(" - backend routing: /api/backend/*");
console.log(" - refresh routing: /api/auth/refresh");
console.log(" - no direct frontend fetch() calls outside client");
