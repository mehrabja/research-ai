"use client";

import Link from "next/link";
import {useSearchParams} from "next/navigation";
import {Suspense,useEffect,useState} from "react";

function ResetPasswordForm(){
  const params=useSearchParams();
  const [token,setToken]=useState("");
  const [password,setPassword]=useState("");
  const [confirm,setConfirm]=useState("");
  const [error,setError]=useState("");
  const [done,setDone]=useState(false);
  const [busy,setBusy]=useState(false);
  useEffect(()=>setToken(params.get("token")??""),[params]);

  async function submit(e:React.FormEvent){
    e.preventDefault();setError("");
    if(password.length<15){setError("Password must be at least 15 characters.");return}
    if(password!==confirm){setError("Passwords do not match.");return}
    setBusy(true);
    try{
      const res=await fetch("/api/backend/auth/password-reset/confirm",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({token,new_password:password})});
      const body=await res.json().catch(()=>({}));
      if(!res.ok)throw new Error(typeof body?.detail==="string"?body.detail:"Password reset failed.");
      setDone(true);
    }catch(e){setError(e instanceof Error?e.message:"Password reset failed.");}
    finally{setBusy(false);}
  }

  return <div className="auth-page">
    <section className="auth-side"><Link className="brand" href="/"><span className="brand-mark">R</span><span>Research AI</span></Link><div className="eyebrow" style={{marginTop:70}}>Password security</div><h1>Choose a new account password.</h1><p>Reset tokens are single-use, time-limited and stored only as hashes.</p></section>
    <section className="auth-main"><div className="auth-card"><h2>Reset password</h2>{error&&<div className="notice error" style={{marginTop:14}}>{error}</div>}{done?<><div className="notice success" style={{marginTop:14}}>Password reset completed.</div><Link className="btn primary" href="/login" style={{marginTop:14,display:"inline-block"}}>Return to login</Link></>:<form className="auth-form" onSubmit={submit}><div className="field"><label htmlFor="reset-token">Reset token</label><input id="reset-token" className="input" value={token} onChange={e=>setToken(e.target.value)} required/></div><div className="field"><label htmlFor="new-password">New password</label><input id="new-password" className="input" type="password" value={password} onChange={e=>setPassword(e.target.value)} minLength={15} required/></div><div className="field"><label htmlFor="confirm-password">Confirm password</label><input id="confirm-password" className="input" type="password" value={confirm} onChange={e=>setConfirm(e.target.value)} minLength={15} required/></div><button className="btn primary" disabled={busy||!token}>{busy?"Resetting…":"Reset password"}</button></form>}</div></section>
  </div>;
}

export default function ResetPasswordPage(){
  return <Suspense fallback={<div className="auth-page"><section className="auth-main"><div className="auth-card"><h2>Reset password</h2></div></section></div>}><ResetPasswordForm/></Suspense>;
}
