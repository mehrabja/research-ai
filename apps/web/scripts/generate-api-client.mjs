import { execFile } from "node:child_process";
import { promisify } from "node:util";
import fs from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const exec = promisify(execFile);

const apiUrl =
process.env.API_OPENAPI_URL ?? "http://localhost:8000/openapi.json";

const outputPath = fileURLToPath(
new URL("../src/lib/api/generated.ts", import.meta.url),
);

const tempPath = path.join(tmpdir(), "research-ai-openapi.json");

const response = await fetch(apiUrl);

if (!response.ok) {
throw new Error(
`OpenAPI fetch failed: ${response.status} ${response.statusText}`,
);
}

const openapi = await response.text();

await fs.writeFile(tempPath, openapi, "utf8");

try {
const executable =
process.platform === "win32" ? "npx.cmd" : "npx";

await exec(
executable,
[
"openapi-typescript",
tempPath,
"-o",
outputPath,
],
{
shell: process.platform === "win32",
windowsHide: false,
},
);

console.log(`Generated ${outputPath}`);
} finally {
await fs.rm(tempPath, { force: true });
}
