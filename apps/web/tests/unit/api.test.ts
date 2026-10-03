import{describe,expect,it,vi}from"vitest";import{api}from"@/lib/api/client";
describe("upload transport",()=>{
  it("reports browser upload progress and preserves multipart transport",async()=>{
    const original=globalThis.XMLHttpRequest;
    const progress:number[]=[];

    class FakeXHR{
      upload={
        loaded:0,
        total:0,
        addEventListener:(_:string,handler:()=>void)=>{this.progressHandler=handler;},
        removeEventListener:(_:string,_handler:()=>void)=>{},
      };
      progressHandler=()=>{};
      status=201;
      responseText=JSON.stringify({id:"f1",project_id:"p1",original_filename:"paper.pdf"});
      withCredentials=false;
      private listeners=new Map<string,()=>void>();

      open(method:string,url:string,_async:boolean){
        expect(method).toBe("POST");
        expect(url).toContain("/api/backend/projects/p1/files");
      }
      setRequestHeader(name:string,_value:string){
        expect(["Accept","X-CSRF-Token"]).toContain(name);
      }
      getResponseHeader(name:string){
        return name==="content-type"?"application/json":name==="X-Request-ID"?"rid-upload":null;
      }
      addEventListener(name:string,handler:()=>void){this.listeners.set(name,handler);}
      send(body:FormData){
        const uploaded=body.get("file");
        expect(uploaded).toBeInstanceOf(File);
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
    }finally{
      Object.defineProperty(globalThis,"XMLHttpRequest",{value:original,writable:true});
    }
  });
});

describe("api client",()=>{it("uses same-origin proxy and propagates backend errors",async()=>{const spy=vi.spyOn(globalThis,"fetch").mockResolvedValueOnce(new Response(JSON.stringify({detail:"denied"}),{status:403}));await expect(api.workspaces()).rejects.toThrow("denied");expect(spy).toHaveBeenCalledWith("/api/backend/workspaces",expect.objectContaining({cache:"no-store"}));spy.mockRestore()});it("keeps FormData uploads multipart instead of forcing JSON",async()=>{const spy=vi.spyOn(globalThis,"fetch").mockResolvedValueOnce(new Response(JSON.stringify({id:"f1"}),{status:201,headers:{"content-type":"application/json"}}));const file=new File(["pdf"],"paper.pdf",{type:"application/pdf"});await api.uploadFile("p1",file);const init=spy.mock.calls[0]?.[1] as RequestInit;expect(init.body).toBeInstanceOf(FormData);expect(new Headers(init.headers).has("content-type")).toBe(false);spy.mockRestore()});it("patches a project through the workspace-scoped endpoint",async()=>{const spy=vi.spyOn(globalThis,"fetch").mockResolvedValueOnce(new Response(JSON.stringify({id:"p1",name:"Updated"}),{status:200,headers:{"content-type":"application/json"}}));await api.updateProject("p1","w1",{name:"Updated"});const [url,init]=spy.mock.calls[0]??[];expect(url).toBe("/api/backend/projects/p1?workspace_id=w1");expect(init?.method).toBe("PATCH");expect(JSON.parse(String((init as RequestInit).body))).toEqual({name:"Updated"});spy.mockRestore()});});