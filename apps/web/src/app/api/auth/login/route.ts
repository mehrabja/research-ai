import {NextResponse} from "next/server";
import {z} from "zod";
import {copySetCookies,setAccessCookie} from "@/lib/server/auth";

const schema=z.object({
  email:z.string().email(),
  password:z.string().min(1),
  two_factor_code:z.string().optional(),
  recovery_code:z.string().optional(),
});

export async function POST(req:Request){
  const parsed=schema.safeParse(await req.json().catch(()=>null));
  if(!parsed.success)return NextResponse.json({detail:"Invalid authentication payload."},{status:422});
  const base=process.env.BACKEND_API_URL??"http://localhost:8000";
  const upstream=await fetch(base+"/api/v1/auth/login",{
    method:"POST",
    headers:{"content-type":"application/json"},
    body:JSON.stringify(parsed.data),
    cache:"no-store",
  });
  const body=await upstream.json().catch(()=>({}));
  if(!upstream.ok)return NextResponse.json(body,{status:upstream.status});
  const out=NextResponse.json({ok:true});
  if(typeof body.access_token==="string")setAccessCookie(out,body.access_token);
  copySetCookies(out,upstream);
  return out;
}