import {NextResponse} from "next/server";
import {cookies} from "next/headers";
import {setAccessCookie,copySetCookies,CSRF_COOKIE,REFRESH_COOKIE} from "@/lib/server/auth";
import {getBackendApiUrl} from "@/lib/server/backend-url";

export async function POST(){
  const base=getBackendApiUrl();
  const jar=await cookies();
  const refreshToken=jar.get(REFRESH_COOKIE)?.value;
  const csrf=jar.get(CSRF_COOKIE)?.value;
  const cookieHeader=[refreshToken ? REFRESH_COOKIE+"="+refreshToken : "", csrf ? CSRF_COOKIE+"="+csrf : ""].filter(Boolean).join("; ");
  const headers=new Headers();
  if(cookieHeader)headers.set("cookie",cookieHeader);
  if(csrf)headers.set("X-CSRF-Token",csrf);
  const upstream=await fetch(base+"/api/v1/auth/refresh",{method:"POST",headers,cache:"no-store"});
  const body=await upstream.json().catch(()=>({}));
  if(!upstream.ok)return NextResponse.json(body,{status:upstream.status});
  const out=NextResponse.json({ok:true});
  if(typeof body.access_token==="string")setAccessCookie(out,body.access_token);
  copySetCookies(out,upstream);
  return out;
}