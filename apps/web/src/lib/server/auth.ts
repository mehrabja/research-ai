import {cookies} from "next/headers";
import {NextResponse} from "next/server";
import {getBackendApiUrl} from "./backend-url";

const ACCESS_COOKIE="research_ai_access_token";
const REFRESH_COOKIE="research_ai_refresh";
const CSRF_COOKIE="research_ai_csrf";

export type User={id:string;email:string;full_name?:string|null};

export async function getServerUser():Promise<User|null>{
  const token=(await cookies()).get(ACCESS_COOKIE)?.value;
  if(!token)return null;
  const base=getBackendApiUrl();
  const res=await fetch(base+"/api/v1/auth/me",{
    headers:{authorization:"Bearer "+token},
    cache:"no-store",
  });
  if(!res.ok)return null;
  return res.json();
}

export function setAccessCookie(
  res:NextResponse,
  token:string,
):void{
  res.cookies.set({
    name:ACCESS_COOKIE,
    value:token,
    httpOnly:true,
    secure:process.env.NODE_ENV==="production",
    sameSite:"lax",
    path:"/",
    maxAge:1800,
  });
}

export function clearAccessCookie(res:NextResponse):void{
  res.cookies.set({
    name:ACCESS_COOKIE,
    value:"",
    httpOnly:true,
    secure:process.env.NODE_ENV==="production",
    sameSite:"lax",
    path:"/",
    maxAge:0,
  });
}

export function copySetCookies(
  res:NextResponse,
  upstream:Response,
):void{
  const headers=upstream.headers as Headers & {getSetCookie?:()=>string[]};
  const cookies=headers.getSetCookie?.()??[];
  if(cookies.length){
    for(const value of cookies)res.headers.append("set-cookie",value);
    return;
  }
  const single=upstream.headers.get("set-cookie");
  if(single)res.headers.append("set-cookie",single);
}

export {ACCESS_COOKIE,REFRESH_COOKIE,CSRF_COOKIE};
