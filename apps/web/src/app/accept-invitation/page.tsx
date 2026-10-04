"use client";

import Link from "next/link";
import {useSearchParams} from "next/navigation";
import {Suspense,useEffect,useState} from "react";
import {api} from "@/lib/api/client";

function AcceptInvitationForm(){
  const params=useSearchParams();
  const [token,setToken]=useState("");
  const [status,setStatus]=useState("");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  useEffect(()=>setToken(params.get("token")??""),[params]);

  async function accept(){
    if(!token){setError("The invitation token is missing.");return;}
    setBusy(true);setError("");setStatus("");
    try{
      const result=await api.acceptInvitation(token);
      setStatus("Invitation accepted. Your role is "+result.role+" and the workspace is now available.");
    }catch(err){
      setError(err instanceof Error?err.message:"Invitation could not be accepted.");
    }finally{setBusy(false);}
  }

  return <div className="auth-page">
    <section className="auth-side"><Link className="brand" href="/"><span className="brand-mark">R</span><span>Research AI</span></Link><div className="eyebrow" style={{marginTop:70}}>Workspace invitation</div><h1>Join a research workspace.</h1><p>The invitation is single-use, time-limited and bound to the email address it was issued to.</p></section>
    <section className="auth-main"><div className="auth-card"><h2>Accept invitation</h2><p className="muted">Sign in with the invited account before accepting.</p>
      {error&&<div className="notice error" style={{marginTop:14}}>{error}</div>}
      {status&&<div className="notice success" style={{marginTop:14}}>{status} <Link href="/dashboard" style={{fontWeight:700}}>Open dashboard</Link></div>}
      <div className="field" style={{marginTop:16}}><label>Invitation token</label><input className="input" value={token} onChange={e=>setToken(e.target.value)} placeholder="Paste invitation token" aria-label="Invitation token"/></div>
      <button className="btn primary" style={{marginTop:14}} disabled={!token||busy} onClick={()=>void accept()}>{busy?"Accepting…":"Accept invitation"}</button>
      <div className="actions" style={{marginTop:14}}><Link className="btn" href="/login">Sign in</Link><Link className="btn" href="/team">Team</Link></div>
    </div></section>
  </div>;
}

export default function AcceptInvitationPage(){
  return <Suspense fallback={<div className="auth-page"><section className="auth-main"><div className="auth-card"><h2>Accept invitation</h2></div></section></div>}><AcceptInvitationForm/></Suspense>;
}
