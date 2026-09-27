"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useSearchParams } from "next/navigation";

export default function ResetPasswordPage() {
  const token=useSearchParams().get("token") ?? "";
  const [password,setPassword]=useState(""); const [done,setDone]=useState(false); const [error,setError]=useState("");
  async function submit(e:FormEvent){e.preventDefault();setError("");const r=await fetch("/api/backend/auth/password-reset/confirm",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({token,new_password:password})});if(r.ok)setDone(true);else{const d=await r.json().catch(()=>({}));setError(d?.detail??"Reset failed.");}}
  return <div className="auth-page"><div className="auth-side"><Link className="brand" href="/"><span className="brand-mark">R</span><span>Research AI</span></Link><h1>Create a new password.</h1><p>Reset links are single-use and expire automatically.</p></div><div className="auth-main"><div className="auth-card"><h2>Reset password</h2>{done?<div className="notice">Password reset completed. <Link href="/login">Sign in</Link>.</div>:<form className="auth-form" onSubmit={submit}><div className="field"><label>New password</label><input className="input" type="password" minLength={15} value={password} onChange={e=>setPassword(e.target.value)} required /></div>{error?<div className="notice error">{error}</div>:null}<button className="btn primary">Reset password</button></form>}</div></div></div>;
}
