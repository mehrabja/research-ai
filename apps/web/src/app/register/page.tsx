"use client";

import Link from "next/link";
import {FormEvent,useState} from "react";
import {useRouter} from "next/navigation";

export default function RegisterPage(){
  const router=useRouter();
  const [firstName,setFirstName]=useState("");
  const [lastName,setLastName]=useState("");
  const [email,setEmail]=useState("");
  const [password,setPassword]=useState("");
  const [workspaceName,setWorkspaceName]=useState("");
  const [agree,setAgree]=useState(false);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);

  async function submit(e:FormEvent){
    e.preventDefault();
    setError("");
    if(!agree){setError("Accept the workspace terms to continue.");return;}
    if(password.length<15){setError("Password must be at least 15 characters.");return;}
    setBusy(true);
    try{
      const full_name=[firstName.trim(),lastName.trim()].filter(Boolean).join(" ");
      const res=await fetch("/api/auth/register",{
        method:"POST",
        headers:{"content-type":"application/json"},
        body:JSON.stringify({
          email,
          password,
          full_name:full_name||undefined,
          workspace_name:workspaceName.trim()||undefined,
        }),
      });
      const body=await res.json().catch(()=>({}));
      if(!res.ok)throw new Error(
        typeof body?.detail==="string"?body.detail:
        typeof body?.message==="string"?body.message:
        "Registration failed."
      );
      router.replace("/verify-email?pending=1");
    }catch(err){
      setError(err instanceof Error?err.message:"Registration failed.");
    }finally{
      setBusy(false);
    }
  }

  return <div className="auth-page">
    <section className="auth-side">
      <Link className="brand" href="/"><span className="brand-mark">R</span><span>Research AI</span></Link>
      <div className="eyebrow" style={{marginTop:70}}>Create a research workspace</div>
      <h1>Bring your papers, data and thinking together.</h1>
      <p>Start with a project, invite collaborators later, and keep the workflow grounded in sources and evidence.</p>
      <div className="grid grid-2" style={{marginTop:34}}>
        <div className="card pad"><div className="tag">Evidence</div><div className="strong" style={{fontSize:24,marginTop:10}}>Traceable</div><div className="muted small">claims to sources</div></div>
        <div className="card pad"><div className="tag">Writing</div><div className="strong" style={{fontSize:24,marginTop:10}}>Versioned</div><div className="muted small">manuscript history</div></div>
      </div>
    </section>

    <section className="auth-main">
      <div className="auth-card">
        <h2>Create your account</h2>
        <div className="muted">Your workspace and owner membership are created by the backend.</div>
        {error&&<div className="notice error" style={{marginTop:14}}>{error}</div>}
        <form className="auth-form" onSubmit={submit}>
          <div className="grid grid-2">
            <div className="field"><label>First name</label><input className="input" value={firstName} onChange={e=>setFirstName(e.target.value)} autoComplete="given-name"/></div>
            <div className="field"><label>Last name</label><input className="input" value={lastName} onChange={e=>setLastName(e.target.value)} autoComplete="family-name"/></div>
          </div>
          <div className="field"><label>Work email</label><input className="input" type="email" value={email} onChange={e=>setEmail(e.target.value)} autoComplete="email" required/></div>
          <div className="field"><label>Password</label><input className="input" type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="new-password" minLength={15} required/><div className="muted tiny">Minimum 15 characters.</div></div>
          <div className="field"><label>Workspace name</label><input className="input" value={workspaceName} onChange={e=>setWorkspaceName(e.target.value)} placeholder="Neural Research Lab" required/></div>
          <label className="checkbox"><input type="checkbox" checked={agree} onChange={e=>setAgree(e.target.checked)}/> I agree to the workspace terms and data processing policy.</label>
          <button className="btn primary" disabled={busy}>{busy?"Creating…":"Create workspace →"}</button>
          <div className="hint">Already have an account? <Link href="/login">Log in</Link></div>
        </form>
      </div>
    </section>
  </div>;
}
