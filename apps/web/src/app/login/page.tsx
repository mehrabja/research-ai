"use client";

import Link from "next/link";
import {FormEvent,useState} from "react";
import {useRouter} from "next/navigation";

export default function LoginPage(){
  const router=useRouter();
  const [email,setEmail]=useState("");
  const [password,setPassword]=useState("");
  const [code,setCode]=useState("");
  const [recovery,setRecovery]=useState("");
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);

  async function submit(event:FormEvent){
    event.preventDefault();
    setError("");
    setLoading(true);
    try{
      const res=await fetch("/api/auth/login",{
        method:"POST",
        headers:{"content-type":"application/json"},
        body:JSON.stringify({
          email,
          password,
          two_factor_code:code||undefined,
          recovery_code:recovery||undefined,
        }),
      });
      const body=await res.json().catch(()=>({}));
      if(!res.ok)throw new Error(
        typeof body?.detail==="string"?body.detail:
        typeof body?.message==="string"?body.message:
        "Login failed."
      );
      router.replace("/dashboard");
      router.refresh();
    }catch(err){
      setError(err instanceof Error?err.message:"Login failed.");
    }finally{
      setLoading(false);
    }
  }

  return <div className="auth-page">
    <section className="auth-side">
      <Link className="brand" href="/"><span className="brand-mark">R</span><span>Research AI</span></Link>
      <div className="eyebrow" style={{marginTop:70}}>Your research workspace</div>
      <h1>Continue where your evidence left off.</h1>
      <p>Keep papers, source notes, uploaded files, experiments and manuscript versions in one controlled workspace.</p>
      <div className="quote">
        <div className="tag success">Evidence-first</div>
        <p style={{margin:"12px 0 0"}}>Evidence traceability stays visible from discovery through manuscript review.</p>
        <div className="muted small" style={{marginTop:10}}>Research workflow principle</div>
      </div>
    </section>

    <section className="auth-main">
      <div className="auth-card">
        <Link className="brand" href="/" style={{padding:"0 0 8px"}}><span className="brand-mark">R</span><span>Research AI</span></Link>
        <h2>Welcome back</h2>
        <div className="muted">Sign in to your research workspace.</div>
        {error&&<div className="notice error" style={{marginTop:14}}>{error}</div>}

        <form className="auth-form" onSubmit={submit}>
          <div className="field"><label>Email</label><input className="input" type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} required/></div>
          <div className="field"><label>Password</label><input className="input" type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required/></div>
          <div className="row">
            <span className="muted small">Secure session via HttpOnly refresh cookie</span>
            <Link className="muted small" href="/forgot-password">Forgot password?</Link>
          </div>
          <div className="field"><label>2FA code <span className="muted tiny">when enabled</span></label><input className="input" inputMode="numeric" maxLength={6} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,""))}/></div>
          <div className="field"><label>Recovery code <span className="muted tiny">optional alternative</span></label><input className="input" value={recovery} onChange={e=>setRecovery(e.target.value)}/></div>
          <button className="btn primary" disabled={loading}>{loading?"Signing in…":"Log in"}</button>
          <div className="divider">or</div>
          <div className="socials">
            <a className="btn" href="/api/backend/auth/oauth/google/start">Continue with Google</a>
            <a className="btn" href="/api/backend/auth/oauth/github/start">Continue with GitHub</a>
          </div>
          <div className="hint">No account? <Link href="/register">Create one</Link></div>
        </form>
      </div>
    </section>
  </div>;
}
