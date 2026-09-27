"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

export default function SignupPage() {
  const [email,setEmail]=useState(""); const [password,setPassword]=useState(""); const [name,setName]=useState(""); const [error,setError]=useState(""); const [done,setDone]=useState(false); const [loading,setLoading]=useState(false);
  async function submit(event:FormEvent){
    event.preventDefault(); setLoading(true); setError("");
    try{
      const response=await fetch("/api/auth/register",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({email,password,full_name:name})});
      if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data?.detail ?? data?.message ?? "Registration failed.");}
      setDone(true);
    }catch(e){setError(e instanceof Error?e.message:"Registration failed.");} finally{setLoading(false);}
  }
  return <div className="auth-page"><div className="auth-side"><Link className="brand" href="/"><span className="brand-mark">R</span><span>Research AI</span></Link><h1>Start with a research workspace.</h1><p>Create an account, verify your email when delivery is configured, and continue into the research operating system.</p></div><div className="auth-main"><div className="auth-card"><h2>Create account</h2><p className="muted small">Production accounts are backed by the API and durable job system.</p>{error?<div className="notice error" style={{marginTop:14}}>{error}</div>:null}{done?<div className="notice" style={{marginTop:14}}>Account created. Check your email after the email provider is configured, then sign in.</div>:<form className="auth-form" onSubmit={submit}><div className="field"><label>Full name</label><input className="input" value={name} onChange={e=>setName(e.target.value)} /></div><div className="field"><label>Work email</label><input className="input" type="email" value={email} onChange={e=>setEmail(e.target.value)} required /></div><div className="field"><label>Password</label><input className="input" type="password" minLength={15} value={password} onChange={e=>setPassword(e.target.value)} required /></div><button className="btn primary" disabled={loading}>{loading?"Creating…":"Create account"}</button></form>}<div style={{marginTop:14}}><Link className="small muted" href="/login">Already have an account?</Link></div></div></div></div>;
}
