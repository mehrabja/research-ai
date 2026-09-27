import {PrototypeScreen} from "@/components/prototype-screen";

export const dynamic="force-dynamic";

export default async function CatchAllPage({
  params,
}:{
  params:Promise<{segments?:string[]}>;
}){
  const {segments=[]}=await params;
  return <PrototypeScreen segments={segments}/>;
}
