const DEV_BACKEND_API_URL="http://127.0.0.1:8000";

export function getBackendApiUrl():string{
  const configured=process.env.BACKEND_API_URL?.trim();
  if(configured)return configured.replace(/\/$/,"");
  if(process.env.NODE_ENV==="production"){
    throw new Error("BACKEND_API_URL must be configured in production.");
  }
  return DEV_BACKEND_API_URL;
}
