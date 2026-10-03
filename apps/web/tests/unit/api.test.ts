import{describe,expect,it,vi}from"vitest";import{api}from"@/lib/api/client";
describe("upload transport",()=>{
  it("reports upload progress without setting a JSON content type",async()=>{
    const original=globalThis.XMLHttpRequest;
    const progress:number[]=[];
    let sentBody:FormData|undefined;

    class FakeXHR{
      upload={
        loaded:0,
        total:0,
        addEventListener:(_:string,handler:()=>void)=>{this.progressHandler=handler;},
        removeEventListener:(_:string,_handler:()=>void)=>{},
      };
      progressHandler=()=>{};
      status=201;
      responseText=JSON.stringify({
        id:"f1",
        project_id:"p1",
        folder_id:null,
        original_filename:"paper.pdf",
        normalized_filename:"paper.pdf",
        client_mime_type:"application/pdf",
        detected_mime_type:"application/pdf",
        size_bytes:7,
        status:"uploaded",
        file_kind:"pdf",
        created_at:"2026-10-04T00:00:00Z",
        updated_at:"2026-10-04T00:00:00Z",
      });
      withCredentials=false;
      headers=new Map<string,string>();
      private listeners=new Map<string,()=>void>();

      open(method:string,url:string,_async:boolean){
        expect(method).toBe("POST");
        expect(url).toContain("/api/backend/projects/p1/files");
      }
      setRequestHeader(name:string,value:string){
        expect(["Accept","X-CSRF-Token"]).toContain(name);
        expect(name.toLowerCase()).not.toBe("content-type");
        this.headers.set(name,value);
      }
      getResponseHeader(name:string){
        return name==="content-type"?"application/json":name==="X-Request-ID"?"rid-upload":null;
      }
      addEventListener(name:string,handler:()=>void){this.listeners.set(name,handler);}
      send(body:FormData){
        sentBody=body;
        expect(body.get("file")).toBeInstanceOf(File);
        this.upload.total=7;
        this.upload.loaded=7;
        this.progressHandler();
        this.listeners.get("load")?.();
      }
      abort(){this.listeners.get("abort")?.();}
    }

    Object.defineProperty(globalThis,"XMLHttpRequest",{value:FakeXHR,writable:true});
    try{
      const file=new File(["pdfdata"],"paper.pdf",{type:"application/pdf"});
      const result=await api.uploadFile("p1",file,{onProgress:value=>progress.push(value.percent)});
      expect(result.id).toBe("f1");
      expect(progress).toEqual([100]);
      expect(sentBody?.get("file")).toBeInstanceOf(File);
    }finally{
      Object.defineProperty(globalThis,"XMLHttpRequest",{value:original,writable:true});
    }
  });
});

describe("api client",()=>{it("uses same-origin proxy and propagates backend errors",async()=>{const spy=vi.spyOn(globalThis,"fetch").mockResolvedValueOnce(new Response(JSON.stringify({detail:"denied"}),{status:403}));await expect(api.workspaces()).rejects.toThrow("denied");expect(spy).toHaveBeenCalledWith("/api/backend/workspaces",expect.objectContaining({cache:"no-store"}));spy.mockRestore()});it("keeps JSON transport for ordinary requests",async()=>{const spy=vi.spyOn(globalThis,"fetch").mockResolvedValueOnce(new Response(JSON.stringify({items:[],total:0}),{status:200,headers:{"content-type":"application/json"}}));await api.workspaces();const init=spy.mock.calls[0]?.[1] as RequestInit;expect(new Headers(init.headers).get("content-type")).toBeUndefined();spy.mockRestore()});it("patches a project through the workspace-scoped endpoint",async()=>{const spy=vi.spyOn(globalThis,"fetch").mockResolvedValueOnce(new Response(JSON.stringify({id:"p1",name:"Updated"}),{status:200,headers:{"content-type":"application/json"}}));await api.updateProject("p1","w1",{name:"Updated"});const [url,init]=spy.mock.calls[0]??[];expect(url).toBe("/api/backend/projects/p1?workspace_id=w1");expect(init?.method).toBe("PATCH");expect(JSON.parse(String((init as RequestInit).body))).toEqual({name:"Updated"});spy.mockRestore()});});