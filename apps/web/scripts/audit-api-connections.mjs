import fs from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";

const root=path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const srcRoot=path.join(root,"src");
const routesPath=path.join(srcRoot,"lib","api","routes.ts");
const clientPath=path.join(srcRoot,"lib","api","client.ts");

async function walk(dir){
  const entries=await fs.readdir(dir,{withFileTypes:true});
  const files=[];
  for(const entry of entries){
    if(entry.name==="node_modules"||entry.name===".next")continue;
    const full=path.join(dir,entry.name);
    if(entry.isDirectory())files.push(...await walk(full));
    else if(/\.(ts|tsx|mjs)$/.test(entry.name))files.push(full);
  }
  return files;
}

const [routesSource,clientSource,files]=await Promise.all([
  fs.readFile(routesPath,"utf8"),
  fs.readFile(clientPath,"utf8"),
  walk(srcRoot),
]);

const appShellSource=await fs.readFile(path.join(srcRoot,"components","app-shell.tsx"),"utf8");
const protectedRoot=path.join(srcRoot,"app","(protected)");


const routeNames=[...routesSource.matchAll(/^\s{2}([A-Za-z0-9_]+)\s*:/gm)].map(m=>m[1]);
const uniqueRouteNames=[...new Set(routeNames)];
const referenced=new Set([...clientSource.matchAll(/\broutes\.([A-Za-z0-9_]+)\b/g)].map(m=>m[1]));
const unused=uniqueRouteNames.filter(name=>!referenced.has(name));
const navPaths=[...appShellSource.matchAll(/\["(\/[^"]+)","[^"]*","[^"]+"\]/g)].map(m=>m[1]);
const missingPages=[];
for(const route of navPaths){
  const segment=route.slice(1);
  if(!segment||segment.includes("["))continue;
  try{
    await fs.access(path.join(protectedRoot,segment,"page.tsx"));
  }catch{
    missingPages.push(route);
  }
}

const violations=[];
for(const file of files){
  const rel=path.relative(root,file).replaceAll(path.sep,"/");
  if(
    rel==="src/lib/server/backend-url.ts"||
    rel==="src/lib/api/generated.openapi.ts"||
    rel==="src/app/api/backend/[...path]/route.ts"||
    rel.startsWith("src/app/api/auth/")
  )continue;
  const text=await fs.readFile(file,"utf8");
  if(text.includes("https://api.openai.com")||text.includes("https://openrouter.ai")){
    violations.push(rel+": direct AI provider URL in frontend source");
  }
  if(text.includes("/api/v1/")){
    violations.push(rel+": direct /api/v1 backend path in frontend source; use /api/backend proxy");
  }
  if(/localStorage\.(?:setItem|getItem|removeItem)\([^)]*research_ai_(?:access_token|refresh)/i.test(text)){
    violations.push(rel+": auth token stored/read from browser storage");
  }
}

if(unused.length||violations.length||missingPages.length){
  console.error("Frontend API connection audit failed.");
  if(unused.length)console.error("Unused route builders:",unused.join(", "));
  if(missingPages.length)console.error("Protected nav routes without page.tsx:",missingPages.join(", "));
  if(violations.length)console.error("Connection boundary violations:",violations.join("\n"));
  process.exit(1);
}

console.log("Frontend API connection audit: PASS");
console.log("Route builders:",uniqueRouteNames.length);
console.log("Client references:",referenced.size);
console.log("Direct provider/backend/auth-storage violations: 0");