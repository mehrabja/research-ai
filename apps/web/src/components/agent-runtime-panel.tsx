"use client";

import {useEffect,useMemo,useState} from "react";
import type {FormEvent} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {ApiRequestError,api} from "@/lib/api/client";

type Props={reportId:string};
const ACTIVE_SESSION_STATES=new Set(["queued","running","awaiting_approval"]);
const STREAMING_SESSION_STATES=new Set(["queued","running"]);
const BUSY_SESSION_STATES=new Set(["queued","running","awaiting_approval","archived"]);
const LIVE_TOOL_STATES=new Set(["pending","queued","running"]);

function statusClass(status:string):string {
  if(status==="completed"||status==="idle"||status==="rejected") return "is-success";
  if(status==="failed") return "is-danger";
  if(status==="awaiting_approval"||status==="pending") return "is-warning";
  if(status==="queued"||status==="running") return "is-running";
  return "";
}

function prettyToolName(value:string):string {
  return value.replaceAll("_"," ");
}

function errorText(error:unknown):string {
  return error instanceof Error?error.message:"The request could not be completed.";
}

export function AgentRuntimePanel({reportId}:Props) {
  const queryClient=useQueryClient();
  const [selectedSessionId,setSelectedSessionId]=useState<string|null>(null);
  const [draft,setDraft]=useState("");
  const [liveAssistantText,setLiveAssistantText]=useState("");
  const [liveStreamFailed,setLiveStreamFailed]=useState(false);
  const [liveContextNotice,setLiveContextNotice]=useState("");

  const sessions=useQuery({
    queryKey:["agent-runtime-sessions",reportId],
    queryFn:()=>api.agentRuntimeSessions(reportId),
    enabled:Boolean(reportId),
    retry:false,
    refetchInterval:query=>(query.state.data??[]).some(item=>ACTIVE_SESSION_STATES.has(item.status))?2500:false,
  });

  useEffect(()=>{
    setSelectedSessionId(null);
    setDraft("");
  },[reportId]);

  useEffect(()=>{
    const items=sessions.data;
    if(!items) return;
    const selectedStillExists=selectedSessionId&&items.some(item=>item.id===selectedSessionId);
    if(selectedStillExists) return;
    const preferred=items.find(item=>item.status!=="archived")??items[0];
    setSelectedSessionId(preferred?.id??null);
  },[sessions.data,selectedSessionId]);

  const sessionQuery=useQuery({
    queryKey:["agent-runtime-session",reportId,selectedSessionId],
    queryFn:()=>api.agentRuntimeSession(reportId,selectedSessionId!),
    enabled:Boolean(reportId&&selectedSessionId),
    retry:false,
    refetchInterval:query=>ACTIVE_SESSION_STATES.has(query.state.data?.status??"")?1800:false,
  });
  const selectedSummary=sessions.data?.find(item=>item.id===selectedSessionId);
  const session=sessionQuery.data??selectedSummary;

  const messages=useQuery({
    queryKey:["agent-runtime-messages",reportId,selectedSessionId],
    queryFn:()=>api.agentRuntimeMessages(reportId,selectedSessionId!),
    enabled:Boolean(reportId&&selectedSessionId),
    retry:false,
    refetchInterval:session&&ACTIVE_SESSION_STATES.has(session.status)?1800:false,
  });
  const toolCalls=useQuery({
    queryKey:["agent-runtime-tool-calls",reportId,selectedSessionId],
    queryFn:()=>api.agentRuntimeToolCalls(reportId,selectedSessionId!),
    enabled:Boolean(reportId&&selectedSessionId),
    retry:false,
    refetchInterval:query=>{
      const hasLive=(query.state.data?.items??[]).some(item=>LIVE_TOOL_STATES.has(item.status));
      return hasLive||(session&&ACTIVE_SESSION_STATES.has(session.status))?1800:false;
    },
  });

  const checkpoints=useQuery({
    queryKey:["agent-runtime-checkpoints",reportId,selectedSessionId],
    queryFn:()=>api.agentRuntimeCheckpoints(reportId,selectedSessionId!),
    enabled:Boolean(reportId&&selectedSessionId),
    retry:false,
  });

  const refreshSession=()=>{
    void queryClient.invalidateQueries({queryKey:["agent-runtime-sessions",reportId]});
    if(!selectedSessionId) return;
    void queryClient.invalidateQueries({queryKey:["agent-runtime-session",reportId,selectedSessionId]});
    void queryClient.invalidateQueries({queryKey:["agent-runtime-messages",reportId,selectedSessionId]});
    void queryClient.invalidateQueries({queryKey:["agent-runtime-tool-calls",reportId,selectedSessionId]});
  };

  useEffect(()=>{
    setLiveAssistantText("");
    setLiveStreamFailed(false);
    setLiveContextNotice("");
  },[selectedSessionId]);

  useEffect(()=>{
    if(!selectedSessionId||!session||!STREAMING_SESSION_STATES.has(session.status)) return;
    const stream=new EventSource(api.agentRuntimeEventStreamUrl(reportId,selectedSessionId));
    stream.onmessage=message=>{
      let event:unknown;
      try{event=JSON.parse(message.data) as unknown;}catch{return;}
      if(!event||typeof event!=="object"||Array.isArray(event)) return;
      const record=event as Record<string,unknown>;
      const payload=record.payload&&typeof record.payload==="object"&&!Array.isArray(record.payload)
        ?record.payload as Record<string,unknown>:{};
      switch(record.type){
        case "turn_started":
          setLiveAssistantText("");
          setLiveStreamFailed(false);
          setLiveContextNotice("");
          break;
        case "text_delta":
          if(typeof payload.text==="string") setLiveAssistantText(previous=>previous+payload.text);
          break;
        case "context_compacted":
          setLiveContextNotice(
            "Long-session context was compacted through message "+
            String(payload.through_message_sequence??"unknown")+
            ". The original transcript remains available."
          );
          void queryClient.invalidateQueries({queryKey:["agent-runtime-checkpoints",reportId,selectedSessionId]});
          break;
        case "checkpoint_created":
          void queryClient.invalidateQueries({queryKey:["agent-runtime-checkpoints",reportId,selectedSessionId]});
          break;
        case "tool_approval_required":
          setLiveAssistantText("");
          void queryClient.invalidateQueries({queryKey:["agent-runtime-tool-calls",reportId,selectedSessionId]});
          void queryClient.invalidateQueries({queryKey:["agent-runtime-session",reportId,selectedSessionId]});
          break;
        case "turn_completed":
          setLiveAssistantText("");
          setLiveStreamFailed(false);
          void queryClient.invalidateQueries({queryKey:["agent-runtime-messages",reportId,selectedSessionId]});
          void queryClient.invalidateQueries({queryKey:["agent-runtime-sessions",reportId]});
          void queryClient.invalidateQueries({queryKey:["agent-runtime-session",reportId,selectedSessionId]});
          break;
        case "turn_failed":
          setLiveStreamFailed(true);
          void queryClient.invalidateQueries({queryKey:["agent-runtime-session",reportId,selectedSessionId]});
          break;
      }
    };
    // EventSource reconnects with Last-Event-ID and replays persisted turn events.
    return ()=>stream.close();
  },[reportId,selectedSessionId,session?.status,queryClient]);

  const createSession=useMutation({
    mutationFn:()=>api.agentRuntimeCreateSession(reportId,{title:"Research assistant"}),
    onSuccess:created=>{
      setSelectedSessionId(created.id);
      setDraft("");
      queryClient.setQueryData(
        ["agent-runtime-sessions",reportId],
        (previous:typeof sessions.data)=>previous?[created,...previous.filter(item=>item.id!==created.id)]:[created],
      );
      void queryClient.invalidateQueries({queryKey:["agent-runtime-sessions",reportId]});
    },
  });
  const sendMessage=useMutation({
    mutationFn:()=>api.agentRuntimeSendMessage(reportId,selectedSessionId!,{content:draft.trim()}),
    onSuccess:accepted=>{
      setDraft("");
      queryClient.setQueryData(
        ["agent-runtime-session",reportId,selectedSessionId],
        (previous:typeof session)=>previous?{...previous,status:accepted.status,revision:accepted.revision,active_job_id:accepted.job_id}:previous,
      );
      refreshSession();
    },
  });
  const approveTool=useMutation({
    mutationFn:(toolCallId:string)=>api.agentRuntimeApproveToolCall(reportId,selectedSessionId!,toolCallId),
    onSuccess:refreshSession,
  });
  const rejectTool=useMutation({
    mutationFn:(toolCallId:string)=>api.agentRuntimeRejectToolCall(reportId,selectedSessionId!,toolCallId),
    onSuccess:refreshSession,
  });

  const orderedMessages=useMemo(
    ()=>[...(messages.data?.items??[])].sort((left,right)=>left.sequence-right.sequence),
    [messages.data?.items],
  );
  const orderedToolCalls=useMemo(
    ()=>[...(toolCalls.data?.items??[])].sort((left,right)=>Date.parse(right.created_at)-Date.parse(left.created_at)),
    [toolCalls.data?.items],
  );

  const busy=Boolean(session&&BUSY_SESSION_STATES.has(session.status));
  const canSend=Boolean(session&&!busy&&draft.trim()&&!sendMessage.isPending);
  const runtimeError=sessions.error??sessionQuery.error;
  const runtimeDisabled=runtimeError instanceof ApiRequestError&&runtimeError.status===404;

  function submitMessage(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if(canSend) sendMessage.mutate();
  }

  return <section className="wb-panel wb-agent-panel" aria-labelledby="wb-agent-title">
    <div className="wb-agent-heading">
      <div>
        <div className="eyebrow">Report-scoped assistant</div>
        <h2 id="wb-agent-title">Agent Runtime</h2>
        <p>Ask the configured research model to work with this report. Any registered tool request is shown here and waits for your approval.</p>
      </div>
      <div className="wb-agent-heading-actions">
        {session&&<span className={"wb-status "+statusClass(session.status)}>{prettyToolName(session.status)}</span>}
        <button className="btn" type="button" onClick={()=>createSession.mutate()} disabled={createSession.isPending||sessions.isPending||runtimeDisabled}>
          {createSession.isPending?"Creating…":"New session"}
        </button>
      </div>
    </div>

    {sessions.isPending?<div className="wb-skeleton"/>:runtimeError?<div className="notice error">
      {runtimeDisabled?"Agent Runtime is not enabled for this deployment.":errorText(runtimeError)}
    </div>:<div className="wb-agent-body">
      {(sessions.data?.length??0)>0&&<label className="wb-agent-session-picker">
        <span>Conversation</span>
        <select className="input" value={selectedSessionId??""} onChange={event=>setSelectedSessionId(event.target.value||null)}>
          {sessions.data?.map(item=><option key={item.id} value={item.id}>{item.title} · {item.status}</option>)}
        </select>
      </label>}

      {!session&&<div className="wb-agent-empty">
        <strong>No Agent session for this report yet</strong>
        <p>Create a session to start a report-scoped conversation. Your project and report remain the context boundary.</p>
        <button className="btn primary" type="button" onClick={()=>createSession.mutate()} disabled={createSession.isPending}>
          {createSession.isPending?"Creating session…":"Create Agent session"}
        </button>
      </div>}

      {session&&<>
        <div className="wb-agent-transcript" aria-live="polite">
          {messages.isPending?<div className="wb-skeleton"/>:messages.isError?<div className="notice error">{errorText(messages.error)}</div>:orderedMessages.length===0?
            <div className="wb-agent-empty"><strong>Session ready</strong><p>Ask a research question or request an analysis grounded in this report.</p></div>:
            orderedMessages.map(message=><article className={"wb-agent-message "+(message.role==="user"?"is-user":"is-assistant")} key={message.id}>
              <header><strong>{message.role==="user"?"You":"Research Agent"}</strong><time>{new Date(message.created_at).toLocaleString()}</time></header>
              <p>{message.content}</p>
              {message.evidence_refs.length>0&&<small>{message.evidence_refs.length} validated evidence reference{message.evidence_refs.length===1?"":"s"}</small>}
              {message.token_usage?.total_tokens!==undefined&&message.token_usage.total_tokens!==null&&<small>{message.token_usage.total_tokens.toLocaleString()} tokens · {message.model_name??"configured model"}</small>}
            </article>)}
          {liveAssistantText&&<article className="wb-agent-message is-assistant is-streaming" aria-live="polite">
            <header><strong>Research Agent · live response</strong></header>
            <p>{liveAssistantText}<span className="wb-agent-stream-cursor" aria-hidden="true">▍</span></p>
            {liveStreamFailed&&<small className="wb-agent-error">Stream interrupted. The saved session state is being recovered.</small>}
          </article>}
          {liveContextNotice&&<p className="wb-agent-muted">{liveContextNotice}</p>}
          {(session.status==="queued"||session.status==="running")&&<div className="wb-agent-pending"><span className="wb-agent-pulse"/> Agent turn {session.status==="queued"?"queued":"running"}…</div>}
        </div>

        <div className="wb-agent-tool-list">
          <div className="wb-agent-subhead">
            <strong>Tool requests and execution</strong>
            <span>{toolCalls.data?.items.length??0} tool requests · {checkpoints.data?.total??0} checkpoints</span>
          </div>
          {toolCalls.isError?<div className="notice error">{errorText(toolCalls.error)}</div>:
            orderedToolCalls.length===0?<p className="wb-agent-muted">No tool requests have been made in this session.</p>:
            orderedToolCalls.map(call=><article className="wb-agent-tool-card" key={call.id}>
              <div className="wb-agent-tool-top">
                <strong>{prettyToolName(call.tool_key)}</strong>
                <span className={"wb-status "+statusClass(call.status)}>{prettyToolName(call.status)}</span>
              </div>
              <p>{call.tool_description}</p>
              <div className="wb-agent-tool-reason"><span>Reason requested by Agent</span>{call.reason}</div>
              <details className="wb-agent-arguments">
                <summary>Review arguments</summary>
                <pre>{JSON.stringify(call.arguments,null,2)}</pre>
              </details>
              {call.status==="pending"&&session.status==="awaiting_approval"&&<div className="wb-agent-decision-note">
                Review the tool, reason and arguments before approving. Nothing runs until you choose an action.
              </div>}
              {call.status==="pending"&&<div className="wb-agent-actions">
                <button className="btn primary" type="button" disabled={approveTool.isPending||rejectTool.isPending} onClick={()=>approveTool.mutate(call.id)}>
                  {approveTool.isPending&&approveTool.variables===call.id?"Queueing…":"Approve and run"}
                </button>
                <button className="btn" type="button" disabled={approveTool.isPending||rejectTool.isPending} onClick={()=>rejectTool.mutate(call.id)}>
                  {rejectTool.isPending&&rejectTool.variables===call.id?"Rejecting…":"Reject"}
                </button>
              </div>}
              {call.status==="completed"&&call.output_preview&&<details className="wb-agent-output">
                <summary>Inspect saved result preview</summary>
                <pre>{JSON.stringify(call.output_preview,null,2)}</pre>
              </details>}
              {call.status==="failed"&&call.error_code&&<small className="wb-agent-error">Execution failed: {call.error_code}</small>}
            </article>)}
          {approveTool.isError&&<div className="notice error">{errorText(approveTool.error)}</div>}
          {rejectTool.isError&&<div className="notice error">{errorText(rejectTool.error)}</div>}
        </div>

        <form className="wb-agent-composer" onSubmit={submitMessage}>
          <label htmlFor="wb-agent-message">Message the research agent</label>
          <textarea
            id="wb-agent-message"
            className="input"
            rows={3}
            maxLength={12000}
            value={draft}
            onChange={event=>setDraft(event.target.value)}
            onKeyDown={event=>{
              if(event.key==="Enter"&&!event.shiftKey){
                event.preventDefault();
                if(canSend) sendMessage.mutate();
              }
            }}
            placeholder="Ask a question about the evidence, request synthesis, or ask the agent to run a supported research tool…"
            disabled={busy||sendMessage.isPending}
          />
          <div className="wb-agent-compose-footer">
            <small>{draft.length.toLocaleString()} / 12,000 characters · Enter to send, Shift+Enter for a new line</small>
            <button className="btn primary" type="submit" disabled={!canSend}>{sendMessage.isPending?"Sending…":"Send message ↗"}</button>
          </div>
          {sendMessage.isError&&<div className="notice error">{errorText(sendMessage.error)}</div>}
          {session.last_error_code&&<div className="wb-agent-error">Last runtime error: {session.last_error_code}</div>}
          {session.status==="awaiting_approval"&&<div className="wb-agent-muted">The conversation is waiting for your decision on the tool request above.</div>}
        </form>
      </>}
      {createSession.isError&&<div className="notice error">{errorText(createSession.error)}</div>}
    </div>}
  </section>;
}
