"use client";

import Link from "next/link";
import {useSearchParams} from "next/navigation";
import {Suspense,useEffect,useState} from "react";

function VerifyEmailForm(){
  const params=useSearchParams();
  const [token,setToken]=useState("");
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  useEffect(()=>{setToken(params.get("token")??"");},[params]);

  async function verify(){
    setBusy(true);setError("");setMessage("");
    try{
      const res=await fetch("/api/backend/auth/verify-email",{
        method:"POST",
        headers:{"content-type":"application/json"},
        body:JSON.stringify({token}),
      });
      const body=await res.json().catch(()=>({}));
      if(!res.ok)throw new Error(typeof body?.detail==="string"?body.detail:"Verification failed.");
      setMessage("Email verified. You can now sign in.");
    }catch(e){setError(e instanceof Error?e.message:"Verification failed.");}
    finally{setBusy(false);}
  }

  return <div className="auth-page">
    <section className="auth-side"><Link className="brand" href="/"><span className="brand-mark">R</span><span>Research AI</span></Link><div className="eyebrow" style={{marginTop:70}}>Account security</div><h1>Verify your research workspace.</h1><p>Your account uses a single-use verification token and a durable email delivery job.</p></section>
    <section className="auth-main"><div className="auth-card"><h2>Verify email</h2><p className="muted">Open the link from your verification email.</p>{error&&<div className="notice error" style={{marginTop:14}}>{error}</div>}{message&&<div className="notice success" style={{marginTop:14}}>{message}</div>}<div className="field" style={{marginTop:16}}><label>Verification token</label><input className="input" value={token} onChange={e=>setToken(e.target.value)} placeholder="Paste token from email"/></div><button className="btn primary" style={{marginTop:14}} disabled={!token||busy} onClick={verify}>{busy?"Verifying…":"Verify email"}</button><div className="actions" style={{marginTop:14}}><Link className="btn" href="/login">Sign in</Link><Link className="btn" href="/forgot-password">Reset password</Link></div></div></section>
  </div>;
}

export default function VerifyEmailPage(){
  return <Suspense fallback={<div className="auth-page"><section className="auth-main"><div className="auth-card"><h2>Verify email</h2></div></section></div>}><VerifyEmailForm/></Suspense>;
}
