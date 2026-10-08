"use client";

import Link from "next/link";
import {useState} from "react";

export default function ForgotPasswordPage(){
  const [email,setEmail]=useState("");
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  async function submit(e:React.FormEvent){
    e.preventDefault();setBusy(true);setMessage("");
    try{
      const res=await fetch("/api/backend/auth/password-reset/request",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({email})});
      const body=await res.json().catch(()=>({}));
      if(!res.ok)throw new Error(typeof body?.detail==="string"?body.detail:typeof body?.message==="string"?body.message:"Password reset request failed.");
      setMessage(typeof body?.message==="string"?body.message:"If the account exists, a password reset email will be sent.");
    }catch(err){
      setMessage(err instanceof Error?err.message:"Password reset request failed.");
    }finally{setBusy(false);}
  }
  return <div className="auth-page">
    <section className="auth-side"><Link className="brand" href="/"><span className="brand-mark">R</span><span>Research AI</span></Link><div className="eyebrow" style={{marginTop:70}}>Password recovery</div><h1>Recover access without exposing account existence.</h1><p>The API returns the same response shape whether or not an account exists.</p></section>
    <section className="auth-main"><div className="auth-card"><h2>Forgot password?</h2><p className="muted">Enter your account email.</p>{message&&<div className="notice" style={{marginTop:14}}>{message}</div>}<form className="auth-form" onSubmit={submit}><div className="field"><label htmlFor="forgot-email">Email</label><input id="forgot-email" className="input" type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></div><button className="btn primary" disabled={busy}>{busy?"Sending…":"Send reset link"}</button><div className="hint"><Link href="/login">Back to login</Link></div></form></div></section>
  </div>;
}
