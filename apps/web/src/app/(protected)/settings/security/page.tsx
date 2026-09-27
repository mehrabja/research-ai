"use client";
import{useState}from"react";
import{useMutation,useQuery,useQueryClient}from"@tanstack/react-query";
import{api}from"@/lib/api/client";

export default function SecurityPage(){
 const qc=useQueryClient();
 const [name,setName]=useState("");
 const [created,setCreated]=useState("");
 const [error,setError]=useState("");
 const [setup,setSetup]=useState<{secret:string;provisioning_uri:string;recovery_codes:string[]}|null>(null);
 const [code,setCode]=useState("");
 const tokens=useQuery({queryKey:["api-tokens"],queryFn:api.apiTokens});
 const mfa=useQuery({queryKey:["mfa-status"],queryFn:api.mfaStatus});
 const create=useMutation({mutationFn:()=>api.createAPIToken({name}),onSuccess:r=>{setCreated(r.token);setName("");qc.invalidateQueries({queryKey:["api-tokens"]}),setError("")},onError:e=>setError(e instanceof Error?e.message:String(e))});
 const setupMfa=useMutation({mutationFn:api.mfaSetup,onSuccess:r=>{setSetup(r);setCode("");},onError:e=>setError(e instanceof Error?e.message:String(e))});
 const enableMfa=useMutation({mutationFn:()=>api.mfaEnable(code),onSuccess:()=>{setSetup(null);setCode("");qc.invalidateQueries({queryKey:["mfa-status"]})},onError:e=>setError(e instanceof Error?e.message:String(e))});
 const disableMfa=useMutation({mutationFn:()=>api.mfaDisable(code),onSuccess:()=>{setCode("");qc.invalidateQueries({queryKey:["mfa-status"]})},onError:e=>setError(e instanceof Error?e.message:String(e))});
 return <div className="space-y-7">
  <header><div className="kicker">Security</div><h1 className="text-3xl font-semibold mt-2">Security</h1><p className="muted mt-2">Sessions, personal API credentials, and two-factor authentication.</p></header>
  <section className="card p-5 space-y-4"><div><h2 className="font-semibold">Two-factor authentication</h2><p className="muted text-sm mt-1">{mfa.data?.enabled?"TOTP MFA is enabled.":"TOTP MFA is not enabled."}</p></div>
   {!mfa.data?.enabled&&!setup&&<button className="btn btn-primary" onClick={()=>setupMfa.mutate()} disabled={setupMfa.isPending}>Set up MFA</button>}
   {setup&&<div className="space-y-4"><div className="text-xs font-mono break-all">Secret: {setup.secret}</div><div className="muted text-xs break-all">Provisioning URI: {setup.provisioning_uri}</div><div className="grid md:grid-cols-2 gap-3"><div><div className="muted text-xs mb-2">Enter authenticator code to enable</div><input className="input" inputMode="numeric" value={code} onChange={e=>setCode(e.target.value)} placeholder="123456"/></div><div><div className="muted text-xs mb-2">Recovery codes (store securely)</div><code className="block p-3 rounded-lg text-xs bg-black/30 break-all">{setup.recovery_codes.join("\n")}</code></div></div><button className="btn btn-primary" disabled={enableMfa.isPending||code.length<6} onClick={()=>enableMfa.mutate()}>Enable MFA</button></div>}
   {mfa.data?.enabled&&<div className="grid md:grid-cols-[1fr_auto] gap-3"><input className="input" inputMode="numeric" value={code} onChange={e=>setCode(e.target.value)} placeholder="Current authenticator code"/><button className="btn btn-secondary" disabled={disableMfa.isPending||code.length<6} onClick={()=>disableMfa.mutate()}>Disable MFA</button></div>}
   {mfa.data?.enabled&&<div className="muted text-xs">Recovery codes remaining: {mfa.data.recovery_codes_remaining}</div>}
  </section>
  <section className="card p-5 space-y-4"><div><h2 className="font-semibold">Personal API tokens</h2><p className="muted text-sm mt-1">Tokens are shown once and stored as hashes on the server.</p></div><div className="flex gap-2"><input className="input" value={name} onChange={e=>setName(e.target.value)} placeholder="Token name"/><button className="btn btn-primary" disabled={!name||create.isPending} onClick={()=>create.mutate()}>Create token</button></div>{created&&<code className="block p-3 rounded-lg bg-black/30 break-all text-xs">{created}</code>}<div className="divide-y" style={{borderColor:"var(--line)"}}>{(tokens.data??[]).map(t=><div key={t.id} className="py-3 flex items-center justify-between"><div><div className="text-sm">{t.name}</div><div className="muted text-xs mt-1">{t.token_prefix} · {t.revoked_at?"revoked":"active"}</div></div>{!t.revoked_at&&<button className="btn btn-secondary text-xs" onClick={()=>api.revokeAPIToken(t.id).then(()=>qc.invalidateQueries({queryKey:["api-tokens"]}))}>Revoke</button>}</div>)}</div></section>
  {error&&<div className="text-sm" style={{color:"var(--danger)"}}>{error}</div>}
 </div>
}