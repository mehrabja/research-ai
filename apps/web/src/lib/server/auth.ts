import{cookies}from"next/headers";import{NextResponse}from"next/server";
const ACCESS_COOKIE="research_ai_access_token";const REFRESH_COOKIE="research_ai_refresh_token";
export type User={id:string;email:string};
export async function getServerUser():Promise<User|null>{const token=(await cookies()).get(ACCESS_COOKIE)?.value;if(!token)return null;const base=process.env.BACKEND_API_URL??"http://localhost:8000";const res=await fetch(base+"/api/v1/auth/me",{headers:{authorization:"Bearer "+token},cache:"no-store"});if(!res.ok)return null;return res.json()}
export function setAuthCookies(res:NextResponse,access:string,refresh:string){const secure=process.env.NODE_ENV==="production";res.cookies.set({name:ACCESS_COOKIE,value:access,httpOnly:true,secure,sameSite:"lax",path:"/",maxAge:1800});res.cookies.set({name:REFRESH_COOKIE,value:refresh,httpOnly:true,secure,sameSite:"lax",path:"/",maxAge:60*60*24*30})}
export function setAccessCookie(res:NextResponse,token:string){const secure=process.env.NODE_ENV==="production";res.cookies.set({name:ACCESS_COOKIE,value:token,httpOnly:true,secure,sameSite:"lax",path:"/",maxAge:1800})}
export function clearAuthCookies(res:NextResponse){const secure=process.env.NODE_ENV==="production";res.cookies.set({name:ACCESS_COOKIE,value:"",httpOnly:true,secure,sameSite:"lax",path:"/",maxAge:0});res.cookies.set({name:REFRESH_COOKIE,value:"",httpOnly:true,secure,sameSite:"lax",path:"/",maxAge:0})}
export function clearAccessCookie(res:NextResponse){clearAuthCookies(res)}
export {ACCESS_COOKIE,REFRESH_COOKIE};
