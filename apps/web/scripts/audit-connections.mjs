#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, "..");
const srcRoot = path.join(webRoot, "src");
const clientPath = path.join(srcRoot, "lib", "api", "client.ts");
const backendUrlPath = "src/lib/server/backend-url.ts";

const failures = [];

function isServerBoundary(relative) {
  return relative.startsWith("src/app/api/") || relative.startsWith("src/lib/server/");
}

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (["node_modules", ".next", "dist"].includes(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full);
      continue;
    }
    if (!/\.(ts|tsx)$/.test(entry.name)) continue;

    const source = fs.readFileSync(full, "utf8");
    const relative = path.relative(webRoot, full).replaceAll("\\", "/");

    if (relative !== "src/lib/api/client.ts" && !isServerBoundary(relative)) {
      const fetchCalls = [...source.matchAll(/\bfetch\s*\(\s*["']([^"']+)["']/g)];
      if (/\bfetch\s*\(/.test(source)) {
        if (fetchCalls.length === 0) {
          failures.push(`${relative}: fetch() target is not a literal /api/* route`);
        } else {
          for (const match of fetchCalls) {
            if (!match[1].startsWith("/api/")) {
              failures.push(`${relative}: fetch() must use same-origin /api/* routes outside the central client`);
            }
          }
        }
      }
    }

    if (
      /https?:\/\/localhost:\d+|https?:\/\/127\.0\.0\.1:\d+/.test(source) &&
      relative !== backendUrlPath
    ) {
      failures.push(`${relative}: hard-coded local backend URL`);
    }
  }
}

walk(srcRoot);

const client = fs.readFileSync(clientPath, "utf8");

if (!/async function rawRequest<T>/.test(client)) {
  failures.push("src/lib/api/client.ts: central rawRequest() is missing");
}
if (!/fetch\(["']\/api\/backend\//.test(client)) {
  failures.push("src/lib/api/client.ts: backend requests are not routed through /api/backend");
}
if (!/\/api\/auth\/refresh/.test(client)) {
  failures.push("src/lib/api/client.ts: refresh flow is missing");
}
if ((client.match(/request<[^>]+>\(/g) ?? []).length < 10) {
  failures.push("src/lib/api/client.ts: unexpectedly small typed API surface");
}

const backendUrl = fs.readFileSync(
  path.join(srcRoot, "lib", "server", "backend-url.ts"),
  "utf8",
);
if (!/BACKEND_API_URL/.test(backendUrl)) {
  failures.push("src/lib/server/backend-url.ts: BACKEND_API_URL is not the backend configuration source");
}
if (!/NODE_ENV/.test(backendUrl)) {
  failures.push("src/lib/server/backend-url.ts: production backend configuration guard is missing");
}

if (failures.length) {
  console.error("Frontend API connection audit failed.");
  for (const failure of failures) console.error(" - " + failure);
  process.exit(1);
}

console.log("Frontend API connection audit passed.");
console.log(" - central browser API client: OK");
console.log(" - same-origin /api/* routes: OK");
console.log(" - server API/auth boundaries: OK");
console.log(" - production backend URL guard: OK");
console.log(" - no unauditable external fetch() targets");
