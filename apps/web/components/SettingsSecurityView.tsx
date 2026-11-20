"use client";

import { useRouter } from "next/navigation";
import { apiErrorFromResponse } from "@/lib/api/errors";
import { logoutAll } from "@/lib/api/auth";
import { clearSessionUserCache } from "@/lib/session-cache";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type User = { id: string; email: string; email_verified_at: string | null };
type Session = { id: string; created_at: string; expires_at: string; last_used_at: string | null };
type MFAStatus = { enabled: boolean; recovery_codes_remaining: number };
type MFASetup = { secret: string; provisioning_uri: string; recovery_codes: string[] };
type APIToken = {
  id: string;
  name: string;
  token_prefix: string;
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
  scopes: string[];
  allowed_workspace_ids: string[];
  allowed_project_ids: string[];
};
type CreatedToken = {
  id: string;
  name: string;
  token: string;
  token_prefix: string;
  expires_at: string | null;
  scopes: string[];
  allowed_workspace_ids: string[];
  allowed_project_ids: string[];
};
type OAuthAccount = { provider: string; created_at: string };
type Activity = { id: string; event: string; summary: string; occurred_at: string };

const scopePresets: Array<{ label: string; scopes: string[] }> = [
  { label: "Read only", scopes: ["read:*"] },
  { label: "Read + write", scopes: ["read:*", "write:*"] },
  { label: "Full API access", scopes: ["*"] },
];


async function readJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      "Security request failed.",
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  if (!text) {
    return undefined as T;
  }

  return JSON.parse(text) as T;
}

function formatDate(value: string | null): string {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function SettingsSecurityView() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [tokenName, setTokenName] = useState("");
  const [tokenExpiry, setTokenExpiry] = useState("");
  const [tokenScopes, setTokenScopes] = useState<string[]>(["read:*"]);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteMfaCode, setDeleteMfaCode] = useState("");
  const [createdToken, setCreatedToken] = useState<CreatedToken | null>(null);
  const [mfaSetup, setMfaSetup] = useState<MFASetup | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const userQuery = useQuery({
    queryKey: ["auth-user"],
    queryFn: () => readJson<User>("/api/v1/auth/me"),
  });
  const sessionsQuery = useQuery({
    queryKey: ["auth-sessions"],
    queryFn: () => readJson<Session[]>("/api/v1/auth/sessions"),
  });
  const mfaQuery = useQuery({
    queryKey: ["auth-mfa"],
    queryFn: () => readJson<MFAStatus>("/api/v1/auth/mfa"),
  });
  const tokensQuery = useQuery({
    queryKey: ["auth-api-tokens"],
    queryFn: () => readJson<APIToken[]>("/api/v1/auth/api-tokens"),
  });
  const oauthQuery = useQuery({
    queryKey: ["auth-oauth-accounts"],
    queryFn: () => readJson<OAuthAccount[]>("/api/v1/auth/oauth/accounts"),
  });
  const activityQuery = useQuery({
    queryKey: ["auth-activity"],
    queryFn: () => readJson<Activity[]>("/api/v1/auth/activity?limit=50"),
  });
  const auditQuery = useQuery({
    queryKey: ["auth-audit-log"],
    queryFn: () => readJson<Array<{
      id: string; event_code: string; resource_type: string | null;
      resource_id: string | null; outcome: string; reason: string | null;
      occurred_at: string;
    }>>("/api/v1/auth/audit-log?limit=100"),
  });

  const setupMfa = useMutation({
    mutationFn: () => readJson<MFASetup>("/api/v1/auth/mfa/setup", { method: "POST", body: "{}" }),
    onSuccess: (result) => {
      setMfaSetup(result);
      setMfaCode("");
      setNotice("Authenticator setup is ready. Scan the URI or enter the secret, then verify a code.");
    },
  });

  const enableMfa = useMutation({
    mutationFn: (code: string) =>
      readJson<MFAStatus>("/api/v1/auth/mfa/enable", {
        method: "POST",
        body: JSON.stringify({ code }),
      }),
    onSuccess: () => {
      setMfaSetup(null);
      setMfaCode("");
      setNotice("Two-factor authentication enabled.");
      void queryClient.invalidateQueries({ queryKey: ["auth-mfa"] });
      void queryClient.invalidateQueries({ queryKey: ["auth-activity"] });
    },
  });

  const disableMfa = useMutation({
    mutationFn: (code: string) =>
      readJson<MFAStatus>("/api/v1/auth/mfa/disable", {
        method: "POST",
        body: JSON.stringify({ code }),
      }),
    onSuccess: () => {
      setDisableCode("");
      setNotice("Two-factor authentication disabled.");
      void queryClient.invalidateQueries({ queryKey: ["auth-mfa"] });
      void queryClient.invalidateQueries({ queryKey: ["auth-activity"] });
    },
  });

  const createToken = useMutation({
    mutationFn: () =>
      readJson<CreatedToken>("/api/v1/auth/api-tokens", {
        method: "POST",
        body: JSON.stringify({
          name: tokenName,
          expires_at: tokenExpiry ? new Date(tokenExpiry).toISOString() : null,
          scopes: tokenScopes,
        }),
      }),
    onSuccess: (result) => {
      setCreatedToken(result);
      setTokenName("");
      setTokenExpiry("");
      setTokenScopes(["read:*"]);
      setNotice("The token was created. The raw secret is shown only in this view.");
      void queryClient.invalidateQueries({ queryKey: ["auth-api-tokens"] });
      void queryClient.invalidateQueries({ queryKey: ["auth-activity"] });
    },
  });

  const revokeToken = useMutation({
    mutationFn: (id: string) =>
      readJson<void>("/api/v1/auth/api-tokens/" + id, { method: "DELETE" }),
    onSuccess: () => {
      setNotice("API token revoked.");
      void queryClient.invalidateQueries({ queryKey: ["auth-api-tokens"] });
      void queryClient.invalidateQueries({ queryKey: ["auth-activity"] });
    },
  });

  const revokeSession = useMutation({
    mutationFn: (id: string) =>
      readJson<void>("/api/v1/auth/sessions/" + id, { method: "DELETE" }),
    onSuccess: () => {
      setNotice("Session revoked.");
      void queryClient.invalidateQueries({ queryKey: ["auth-sessions"] });
      void queryClient.invalidateQueries({ queryKey: ["auth-activity"] });
    },
  });

  const logoutAllMutation = useMutation({
    mutationFn: logoutAll,
    onSuccess: () => {
      clearSessionUserCache(queryClient, false);
      router.replace("/login");
    },
  });

  const disconnectOauth = useMutation({
    mutationFn: (provider: string) =>
      readJson<void>("/api/v1/auth/oauth/" + provider, { method: "DELETE" }),
    onSuccess: () => {
      setNotice("Connected account removed.");
      void queryClient.invalidateQueries({ queryKey: ["auth-oauth-accounts"] });
      void queryClient.invalidateQueries({ queryKey: ["auth-activity"] });
    },
  });


  const deleteAccount = useMutation({
    mutationFn: () =>
      readJson<{ message: string }>("/api/v1/auth/account", {
        method: "DELETE",
        body: JSON.stringify({
          password: deletePassword,
          mfa_code: mfa.enabled ? deleteMfaCode : null,
        }),
      }),
    onSuccess: (result) => {
      setNotice(result.message);
      setDeletePassword("");
      setDeleteMfaCode("");
      clearSessionUserCache(queryClient);
      router.replace("/login");
    },
  });

  const exportData = async () => {
    const response = await fetch("/api/v1/auth/data-export", {
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw await apiErrorFromResponse(
        response,
        "Data export failed.",
      );
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "research-ai-data-export.json";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setNotice("Your account data export is ready.");
  };

  const queryErrors = [
    userQuery.error,
    sessionsQuery.error,
    mfaQuery.error,
    tokensQuery.error,
    oauthQuery.error,
    activityQuery.error,
    setupMfa.error,
    enableMfa.error,
    disableMfa.error,
    createToken.error,
    revokeToken.error,
    revokeSession.error,
    disconnectOauth.error,
    auditQuery.error,
    deleteAccount.error,
    logoutAllMutation.error,
  ];
  const error = queryErrors.find((value): value is Error => value instanceof Error);

  const mfa = mfaQuery.data ?? { enabled: false, recovery_codes_remaining: 0 };
  const sessions = sessionsQuery.data ?? [];
  const tokens = tokensQuery.data ?? [];
  const oauthAccounts = oauthQuery.data ?? [];
  const activity = activityQuery.data ?? [];

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Account security</div>
          <h1>Settings</h1>
          <p>Operational authentication, connected accounts, sessions, API access and security activity.</p>
        </div>
      </div>

      {notice && (
        <section className="card pad" role="status" style={{ marginBottom: 16 }}>
          <div className="row">
            <p className="small" style={{ margin: 0 }}>{notice}</p>
            <button className="btn ghost" type="button" onClick={() => setNotice(null)}>Dismiss</button>
          </div>
        </section>
      )}

      {error && (
        <section className="card pad" role="alert" style={{ marginBottom: 16 }}>
          <div className="row">
            <div>
              <h3>Security request failed</h3>
              <p className="muted small" style={{ marginBottom: 0 }}>{error.message}</p>
            </div>
            <button className="btn ghost" type="button" onClick={() => {
              void queryClient.invalidateQueries({ queryKey: ["auth-user"] });
              void queryClient.invalidateQueries({ queryKey: ["auth-sessions"] });
              void queryClient.invalidateQueries({ queryKey: ["auth-mfa"] });
              void queryClient.invalidateQueries({ queryKey: ["auth-api-tokens"] });
              void queryClient.invalidateQueries({ queryKey: ["auth-oauth-accounts"] });
              void queryClient.invalidateQueries({ queryKey: ["auth-activity"] });
            }}>Retry</button>
          </div>
        </section>
      )}

      <div className="grid grid-2">
        <section className="card pad">
          <div className="row">
            <div>
              <h3>Account</h3>
              <div className="muted small">Authenticated identity and email state.</div>
            </div>
            <span className={"tag " + (userQuery.data?.email_verified_at ? "success" : "")}>
              {userQuery.data?.email_verified_at ? "Verified" : "Verification pending"}
            </span>
          </div>
          <div className="stack" style={{ marginTop: 16 }}>
            <div><div className="small muted">Email</div><b>{userQuery.data?.email ?? "Loading…"}</b></div>
            <div><div className="small muted">User ID</div><code className="small">{userQuery.data?.id ?? "Loading…"}</code></div>
          </div>
        </section>

        <section className="card pad">
          <div className="row">
            <div>
              <h3>Two-factor authentication</h3>
              <div className="muted small">TOTP plus one-time recovery codes.</div>
            </div>
            <span className={"tag " + (mfa.enabled ? "success" : "")}>{mfa.enabled ? "Enabled" : "Disabled"}</span>
          </div>

          {!mfa.enabled && !mfaSetup && (
            <div className="actions" style={{ marginTop: 18 }}>
              <button className="btn primary" type="button" disabled={setupMfa.isPending} onClick={() => setupMfa.mutate()}>
                {setupMfa.isPending ? "Preparing…" : "Set up authenticator"}
              </button>
            </div>
          )}

          {mfaSetup && !mfa.enabled && (
            <div className="stack" style={{ marginTop: 18 }}>
              <div>
                <div className="small muted">Secret</div>
                <code>{mfaSetup.secret}</code>
              </div>
              <div>
                <div className="small muted">Provisioning URI</div>
                <code className="small" style={{ wordBreak: "break-all" }}>{mfaSetup.provisioning_uri}</code>
              </div>
              <div>
                <div className="small muted">Recovery codes</div>
                <pre style={{ whiteSpace: "pre-wrap", margin: "6px 0 0" }}>{mfaSetup.recovery_codes.join("\n")}</pre>
              </div>
              <label className="field">
                <span>Authenticator code</span>
                <input className="input" inputMode="numeric" autoComplete="one-time-code" value={mfaCode} onChange={(event) => setMfaCode(event.target.value)} />
              </label>
              <div className="actions">
                <button className="btn primary" type="button" disabled={mfaCode.length < 6 || enableMfa.isPending} onClick={() => enableMfa.mutate(mfaCode)}>
                  {enableMfa.isPending ? "Verifying…" : "Enable 2FA"}
                </button>
                <button className="btn ghost" type="button" onClick={() => setMfaSetup(null)}>Cancel setup</button>
              </div>
            </div>
          )}

          {mfa.enabled && (
            <div className="stack" style={{ marginTop: 18 }}>
              <div className="row"><span>Recovery codes remaining</span><b>{mfa.recovery_codes_remaining}</b></div>
              <label className="field">
                <span>Code or recovery code to disable</span>
                <input className="input" value={disableCode} onChange={(event) => setDisableCode(event.target.value)} />
              </label>
              <button className="btn" type="button" disabled={disableCode.length < 6 || disableMfa.isPending} onClick={() => disableMfa.mutate(disableCode)}>
                {disableMfa.isPending ? "Disabling…" : "Disable 2FA"}
              </button>
            </div>
          )}
        </section>
      </div>

      <section className="card pad" style={{ marginTop: 16 }}>
        <div className="row">
          <div>
            <h3>Connected accounts</h3>
            <div className="muted small">OAuth identities linked through Google or GitHub sign-in.</div>
          </div>
        </div>
        <div className="grid grid-2" style={{ marginTop: 16 }}>
          {["google", "github"].map((provider) => {
            const account = oauthAccounts.find((item) => item.provider === provider);
            return (
              <article className="card pad" key={provider}>
                <div className="row">
                  <div>
                    <div className="eyebrow">{provider}</div>
                    <h3 style={{ marginTop: 4 }}>{provider === "google" ? "Google" : "GitHub"}</h3>
                  </div>
                  <span className={"tag " + (account ? "success" : "")}>{account ? "Connected" : "Not connected"}</span>
                </div>
                {account && <div className="muted small" style={{ marginTop: 10 }}>Linked {formatDate(account.created_at)}</div>}
                {account && (
                  <button
                    className="btn"
                    style={{ marginTop: 14 }}
                    type="button"
                    disabled={disconnectOauth.isPending}
                    onClick={() => disconnectOauth.mutate(provider)}
                  >
                    {disconnectOauth.isPending && disconnectOauth.variables === provider ? "Removing…" : "Remove account"}
                  </button>
                )}
              </article>
            );
          })}
        </div>
      </section>

      <section className="card pad" style={{ marginTop: 16 }}>
        <div className="row">
          <div>
            <h3>Active sessions</h3>
            <div className="muted small">Refresh sessions stored server-side and independently revocable.</div>
          </div>
          <div className="actions">
            <span className="tag">{sessions.length} active</span>
            <button
              className="btn ghost"
              type="button"
              disabled={logoutAllMutation.isPending}
              onClick={() => logoutAllMutation.mutate()}
            >
              {logoutAllMutation.isPending ? "Signing out…" : "Sign out all"}
            </button>
          </div>
        </div>
        <div className="stack" style={{ marginTop: 14 }}>
          {sessions.map((session) => (
            <div className="list-item" key={session.id}>
              <div className="row">
                <div>
                  <strong>Session</strong>
                  <div className="muted tiny">Created {formatDate(session.created_at)}</div>
                  <div className="muted tiny">Expires {formatDate(session.expires_at)}</div>
                  {session.last_used_at && <div className="muted tiny">Last used {formatDate(session.last_used_at)}</div>}
                </div>
                <button className="btn" type="button" disabled={revokeSession.isPending} onClick={() => revokeSession.mutate(session.id)}>
                  {revokeSession.isPending && revokeSession.variables === session.id ? "Revoking…" : "Revoke"}
                </button>
              </div>
            </div>
          ))}
          {sessions.length === 0 && <p className="muted small">No active refresh sessions are visible.</p>}
        </div>
      </section>

      <section className="card pad" style={{ marginTop: 16 }}>
        <div className="row">
          <div>
            <h3>Personal API tokens</h3>
            <div className="muted small">Tokens are hashed at rest and displayed in raw form only once after creation.</div>
          </div>
        </div>

        {createdToken && (
          <div className="card pad" role="alert" style={{ marginTop: 16 }}>
            <h4 style={{ marginTop: 0 }}>Copy this token now</h4>
            <p className="muted small">The raw secret is not returned by the list endpoint and cannot be recovered later.</p>
            <code style={{ display: "block", overflowWrap: "anywhere" }}>{createdToken.token}</code>
            <button className="btn" style={{ marginTop: 12 }} type="button" onClick={() => setCreatedToken(null)}>Hide secret</button>
          </div>
        )}

        <div className="grid grid-3" style={{ marginTop: 16 }}>
          <label className="field">
            <span>Token name</span>
            <input className="input" value={tokenName} onChange={(event) => setTokenName(event.target.value)} placeholder="CLI access" maxLength={120} />
          </label>
          <label className="field">
            <span>Expiry (optional)</span>
            <input className="input" type="datetime-local" value={tokenExpiry} onChange={(event) => setTokenExpiry(event.target.value)} />
          </label>
          <label className="field">
            <span>Permissions</span>
            <select className="input" value={scopePresets.find((preset) => JSON.stringify(preset.scopes) === JSON.stringify(tokenScopes))?.label ?? "custom"} onChange={(event) => {
              const preset = scopePresets.find((item) => item.label === event.target.value);
              if (preset) setTokenScopes(preset.scopes);
            }}>
              {scopePresets.map((preset) => <option key={preset.label}>{preset.label}</option>)}
            </select>
          </label>
          <div className="actions" style={{ alignItems: "end" }}>
            <button className="btn primary" type="button" disabled={!tokenName.trim() || createToken.isPending} onClick={() => createToken.mutate()}>
              {createToken.isPending ? "Creating…" : "Create token"}
            </button>
          </div>
        </div>

        <div className="stack" style={{ marginTop: 16 }}>
          {tokens.map((token) => (
            <div className="list-item" key={token.id}>
              <div className="row">
                <div>
                  <strong>{token.name}</strong>
                  <div className="muted tiny">{token.token_prefix} · {token.scopes.join(", ")} · created {formatDate(token.created_at)}</div>
                  <div className="muted tiny">{token.revoked_at ? "Revoked " + formatDate(token.revoked_at) : token.expires_at ? "Expires " + formatDate(token.expires_at) : "No expiry"}</div>
                  {token.last_used_at && <div className="muted tiny">Last used {formatDate(token.last_used_at)}</div>}
                </div>
                {!token.revoked_at && (
                  <button className="btn" type="button" disabled={revokeToken.isPending} onClick={() => revokeToken.mutate(token.id)}>
                    {revokeToken.isPending && revokeToken.variables === token.id ? "Revoking…" : "Revoke"}
                  </button>
                )}
              </div>
            </div>
          ))}
          {tokens.length === 0 && <p className="muted small">No personal API tokens.</p>}
        </div>
      </section>

      <section className="card pad" style={{ marginTop: 16 }}>
        <div className="row">
          <div>
            <h3>Security activity</h3>
            <div className="muted small">A safe user-facing projection of durable account security events; raw audit logs remain server-side.</div>
          </div>
          <span className="tag">{activity.length} recent</span>
        </div>
        <div className="stack" style={{ marginTop: 14 }}>
          {activity.map((item) => (
            <div className="list-item" key={item.id}>
              <div className="row">
                <strong>{item.summary}</strong>
                <span className="muted tiny">{formatDate(item.occurred_at)}</span>
              </div>
            </div>
          ))}
          {activity.length === 0 && <p className="muted small">No security activity recorded yet.</p>}
        </div>
      </section>

      <div className="grid grid-2" style={{ marginTop: 16 }}>
        <section className="card pad">
          <div className="row">
            <div>
              <h3>Audit log</h3>
              <div className="muted small">Durable security events associated with this account.</div>
            </div>
            <span className="tag">{auditQuery.data?.length ?? 0} events</span>
          </div>
          <div className="stack" style={{ marginTop: 14 }}>
            {(auditQuery.data ?? []).slice(0, 20).map((item) => (
              <div className="list-item" key={item.id}>
                <div className="row">
                  <strong>{item.event_code}</strong>
                  <span className="muted tiny">{formatDate(item.occurred_at)}</span>
                </div>
                <div className="muted tiny">{item.reason ?? item.outcome}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="card pad">
          <div className="row">
            <div>
              <h3>Privacy & account data</h3>
              <div className="muted small">Export portable metadata or permanently deactivate this account.</div>
            </div>
          </div>
          <div className="actions" style={{ marginTop: 16 }}>
            <button className="btn" type="button" onClick={() => void exportData()}>
              Export my data
            </button>
          </div>
          <div className="stack" style={{ marginTop: 18 }}>
            <label className="field">
              <span>Current password</span>
              <input className="input" type="password" autoComplete="current-password" value={deletePassword} onChange={(event) => setDeletePassword(event.target.value)} />
            </label>
            {mfa.enabled && (
              <label className="field">
                <span>MFA code</span>
                <input className="input" inputMode="numeric" value={deleteMfaCode} onChange={(event) => setDeleteMfaCode(event.target.value)} />
              </label>
            )}
            <button
              className="btn"
              type="button"
              disabled={!deletePassword || (mfa.enabled && !deleteMfaCode) || deleteAccount.isPending}
              onClick={() => {
                if (window.confirm("Permanently delete this account and its access credentials?")) {
                  deleteAccount.mutate();
                }
              }}
            >
              {deleteAccount.isPending ? "Deleting…" : "Delete account"}
            </button>
          </div>
        </section>
      </div>
    </>
  );
}
