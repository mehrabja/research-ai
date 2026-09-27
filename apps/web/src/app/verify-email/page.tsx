"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

export default function VerifyEmailPage() {
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [state,setState]=useState<"loading"|"done"|"error">("loading");
  useEffect(()=>{ if(!token){setState("error");return;} fetch("/api/backend/auth/verify-email",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({token})}).then(r=>{setState(r.ok?"done":"error")}).catch(()=>setState("error")); },[token]);
  return <div className="auth-page"><div className="auth-side"><Link className="brand" href="/"><span className="brand-mark">R</span><span>Research AI</span></Link><h1>Email verification.</h1><p>Verification links are single-use and expire according to the account security policy.</p></div><div className="auth-main"><div className="auth-card"><h2>{state==="loading"?"Verifying…":state==="done"?"Email verified":"Verification failed"}</h2><p className="muted small">{state==="done"?"Your email is verified. Continue to sign in.":"The link may be expired, already used, or invalid."}</p><div style={{marginTop:18}}><Link className="btn primary" href="/login">Continue</Link></div></div></div></div>;
}
