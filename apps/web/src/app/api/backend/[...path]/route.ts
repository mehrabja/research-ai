import {NextResponse} from "next/server";
import {cookies} from "next/headers";
import {getBackendApiUrl} from "@/lib/server/backend-url";

const ACCESS_COOKIE="research_ai_access_token";
const REFRESH_COOKIE="research_ai_refresh";
const CSRF_COOKIE="research_ai_csrf";

async function proxy(req:Request,ctx:{params:Promise<{path:string[]}>}){
  const {path}=await ctx.params;
  const base=getBackendApiUrl();
  const incoming=new URL(req.url);
  const target=base.replace(/\/$/,"")+"/api/v1/"+path.join("/")+incoming.search;
  const jar=await cookies();
  const headers=new Headers(req.headers);
  headers.delete("host");
  headers.delete("content-length");
  const access=jar.get(ACCESS_COOKIE)?.value;
  const refresh=jar.get(REFRESH_COOKIE)?.value;
  const csrf=jar.get(CSRF_COOKIE)?.value;
  if(access)headers.set("authorization","Bearer "+access);
  const cookieHeader=[refresh?REFRESH_COOKIE+"="+refresh:"",csrf?CSRF_COOKIE+"="+csrf:""].filter(Boolean).join("; ");
  if(cookieHeader)headers.set("cookie",cookieHeader);
  if(csrf && !headers.has("X-CSRF-Token") && req.method!=="GET" && req.method!=="HEAD")headers.set("X-CSRF-Token",csrf);
  const method=req.method.toUpperCase();
  const body=method==="GET"||method==="HEAD"?undefined:await req.arrayBuffer();
  const upstream=await fetch(target,{method,headers,body,cache:"no-store",redirect:"manual"});
  const responseHeaders=new Headers(upstream.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("transfer-encoding");
  const out=new NextResponse(upstream.body,{status:upstream.status,headers:responseHeaders});
  const setCookies=(upstream.headers as Headers & {getSetCookie?:()=>string[]}).getSetCookie?.()??[];
  for(const cookie of setCookies)out.headers.append("set-cookie",cookie);
  return out;
}

export const GET=proxy;
export const POST=proxy;
export const PATCH=proxy;
export const PUT=proxy;
export const DELETE=proxy;