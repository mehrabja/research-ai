import {NextResponse} from "next/server";
import {cookies} from "next/headers";
import {clearAccessCookie,copySetCookies,CSRF_COOKIE,REFRESH_COOKIE} from "@/lib/server/auth";
import {getBackendApiUrl} from "@/lib/server/backend-url";

export async function POST(){
  const base=getBackendApiUrl();
  const jar=await cookies();
  const refresh=jar.get(REFRESH_COOKIE)?.value;
  const csrf=jar.get(CSRF_COOKIE)?.value;
  const cookieHeader=[refresh ? REFRESH_COOKIE+"="+refresh : "", csrf ? CSRF_COOKIE+"="+csrf : ""].filter(Boolean).join("; ");
  const headers=new Headers();
  if(cookieHeader)headers.set("cookie",cookieHeader);
  if(csrf)headers.set("X-CSRF-Token",csrf);
  const upstream=await fetch(base+"/api/v1/auth/logout",{method:"POST",headers,cache:"no-store"});
  const out=upstream.status===204
    ? new NextResponse(null,{status:204})
    : NextResponse.json(await upstream.json().catch(()=>({})),{status:upstream.status});
  clearAccessCookie(out);
  copySetCookies(out,upstream);
  return out;
}