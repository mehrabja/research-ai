"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

export default function LoginPage() {
  const [email,setEmail]=useState("");
  const [password,setPassword]=useState("");
  const [code,setCode]=useState("");
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError("");
    try {
      const response = await fetch("/api/auth/login", {
        method:"POST",
        headers:{"content-type":"application/json"},
        body:JSON.stringify({email,password,two_factor_code:code||undefined}),
      });
      if(!response.ok) {
        const data=await response.json().catch(()=>({}));
        throw new Error(data?.detail ?? data?.message ?? "Login failed.");
      }
      window.location.href="/dashboard";
    } catch(e) { setError(e instanceof Error ? e.message : "Login failed."); }
    finally { setLoading(false); }
  }

  return <div className="auth-page"><div className="auth-side"><Link className="brand" href="/"><span className="brand-mark">R</span><span>Research AI</span></Link><h1>Research work that keeps its evidence.</h1><p>Sign in to your workspace and continue from your latest versioned research state.</p></div><div className="auth-main"><div className="auth-card"><h2>Sign in</h2><p className="muted small">Use your Research AI account.</p>{error?<div className="notice error" style={{marginTop:14}}>{error}</div>:null}<form className="auth-form" onSubmit={submit}><div className="field"><label>Email</label><input className="input" type="email" value={email} onChange={e=>setEmail(e.target.value)} required /></div><div className="field"><label>Password</label><input className="input" type="password" value={password} onChange={e=>setPassword(e.target.value)} required /></div><div className="field"><label>2FA code (when enabled)</label><input className="input" inputMode="numeric" maxLength={6} value={code} onChange={e=>setCode(e.target.value)} /></div><button className="btn primary" disabled={loading}>{loading?"Signing in…":"Sign in"}</button></form><div className="row" style={{marginTop:14}}><Link className="small muted" href="/forgot-password">Forgot password?</Link><Link className="small muted" href="/signup">Create account</Link></div><div className="divider" style={{margin:"18px 0"}}>or</div><div className="socials"><a className="btn" href="/api/backend/auth/oauth/google/start">Google</a><a className="btn" href="/api/backend/auth/oauth/github/start">GitHub</a></div></div></div></div>;
}
