import {NextResponse} from "next/server";
import {setAccessCookie,copySetCookies} from "@/lib/server/auth";
import {getBackendApiUrl} from "@/lib/server/backend-url";

export async function GET(req:Request){
  const url=new URL(req.url);
  const code=url.searchParams.get("code");
  const state=url.searchParams.get("state");
  const error=url.searchParams.get("error");
  if(error)return NextResponse.redirect(new URL("/login?oauth_error="+encodeURIComponent(error),url.origin));
  if(!code||!state)return NextResponse.redirect(new URL("/login?oauth_error=missing_callback",url.origin));

  const base=getBackendApiUrl();
  const upstream=await fetch(
    base+"/api/v1/auth/oauth/github/callback?code="+encodeURIComponent(code)+"&state="+encodeURIComponent(state),
    {cache:"no-store",redirect:"manual"},
  );
  if(!upstream.ok)return NextResponse.redirect(new URL("/login?oauth_error=callback_failed",url.origin));
  const body=await upstream.json().catch(()=>({}));
  if(typeof body.access_token!=="string")return NextResponse.redirect(new URL("/login?oauth_error=invalid_session",url.origin));

  const out=NextResponse.redirect(new URL("/dashboard",url.origin));
  setAccessCookie(out,body.access_token);
  copySetCookies(out,upstream);
  return out;
}
