"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

export default function ForgotPasswordPage(){
 const [email,setEmail]=useState(""); const [sent,setSent]=useState(false);
 async function submit(e:FormEvent){e.preventDefault(); await fetch("/api/backend/auth/password-reset/request",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({email})}); setSent(true);}
 return <div className="auth-page"><div className="auth-side"><Link className="brand" href="/"><span className="brand-mark">R</span><span>Research AI</span></Link><h1>Reset access safely.</h1><p>Password reset requests are handled through single-use expiring tokens.</p></div><div className="auth-main"><div className="auth-card"><h2>Forgot password</h2>{sent?<div className="notice">If the account exists, a password-reset email will be sent.</div>:<form className="auth-form" onSubmit={submit}><div className="field"><label>Email</label><input className="input" type="email" value={email} onChange={e=>setEmail(e.target.value)} required /></div><button className="btn primary">Send reset link</button></form>}<div style={{marginTop:14}}><Link className="small muted" href="/login">Back to sign in</Link></div></div></div></div>
}
