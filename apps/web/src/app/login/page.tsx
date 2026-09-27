"use client";
import{useState}from"react";import{useRouter}from"next/navigation";import{z}from"zod";
const schema=z.object({email:z.string().email(),password:z.string().min(1),mfa_code:z.string().optional()});
export default function LoginPage(){
 const r=useRouter(),[e,setE]=useState(""),[p,setP]=useState(""),[m,setM]=useState(""),[err,setErr]=useState(""),[busy,setBusy]=useState(false);
 async function submit(ev:React.FormEvent){ev.preventDefault();setErr("");const parsed=schema.safeParse({email:e,password:p,mfa_code:m||undefined});if(!parsed.success){setErr("Enter a valid email and password.");return}setBusy(true);const res=await fetch("/api/auth/login",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(parsed.data)});const body=await res.json().catch(()=>({}));setBusy(false);if(!res.ok){setErr(body?.error?.message??body?.detail??body?.message??"Login failed.");return}r.replace("/dashboard");r.refresh()}
 return <main className="min-h-screen grid place-items-center px-6"><form onSubmit={submit} className="card w-full max-w-md p-7 space-y-5">
  <div><div className="kicker">Research AI</div><h1 className="text-2xl font-semibold mt-2">Sign in</h1><p className="muted text-sm mt-1">Evidence-grounded research workspace.</p></div>
  <label className="block text-sm space-y-2">Email<input className="input" type="email" value={e} onChange={x=>setE(x.target.value)} autoComplete="email"/></label>
  <label className="block text-sm space-y-2">Password<input className="input" type="password" value={p} onChange={x=>setP(x.target.value)} autoComplete="current-password"/></label>
  <label className="block text-sm space-y-2">MFA code <span className="muted">(when enabled)</span><input className="input" inputMode="numeric" value={m} onChange={x=>setM(x.target.value)} autoComplete="one-time-code"/></label>
  {err&&<div className="text-sm" style={{color:"var(--danger)"}}>{err}</div>}
  <button className="btn btn-primary w-full" disabled={busy}>{busy?"Signing in…":"Sign in"}</button>
  <div className="grid grid-cols-2 gap-2"><a className="btn btn-secondary text-center" href="/api/backend/auth/oauth/google/start">Google</a><a className="btn btn-secondary text-center" href="/api/backend/auth/oauth/github/start">GitHub</a></div>
  <p className="muted text-sm">No account? <a className="underline text-white" href="/register">Create one</a></p>
  <a className="muted text-xs underline" href="/password-reset">Forgot password?</a>
 </form></main>
}