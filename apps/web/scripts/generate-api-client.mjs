import{execFile}from"node:child_process";import{promisify}from"node:util";import fs from"node:fs/promises";import os from"node:os";import path from"node:path";import{fileURLToPath}from"node:url";

const exec=promisify(execFile);
const backend=process.env.BACKEND_API_URL?.trim().replace(/\/$/,"")??"http://127.0.0.1:8000";
const url=process.env.API_OPENAPI_URL?.trim()??backend+"/openapi.json";
const out=fileURLToPath(new URL("../src/lib/api/generated.openapi.ts",import.meta.url));
const tmp=path.join(os.tmpdir(),"research-ai-openapi.json");

const res=await fetch(url);
if(!res.ok)throw new Error("OpenAPI fetch failed: "+res.status+" "+url);
await fs.writeFile(tmp,await res.text(),"utf8");

const cli=path.join(process.cwd(),"node_modules","openapi-typescript","bin","cli.js");
await exec(process.execPath,[cli,tmp,"-o",out]);

console.log("Generated",out);
console.log("OpenAPI source",url);
