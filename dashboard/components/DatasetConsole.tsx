"use client";
import { useState } from "react";

const API=process.env.NEXT_PUBLIC_API_BASE_URL??"http://127.0.0.1:8000";
type Source={id:string;name:string;purpose:string;url:string;account_required:boolean;limitations:string};
type Import={id:string;dataset_id:string;imported_at:string;summary:Record<string,unknown>};
type Data={catalog:Source[];imports:Import[]};

export default function DatasetConsole(){
  const [token,setToken]=useState("");
  const [data,setData]=useState<Data|null>(null);
  const [status,setStatus]=useState("");
  const [busy,setBusy]=useState(false);
  async function load(){
    setBusy(true);setStatus("");
    try{
      const response=await fetch(`${API}/v1/datasets`,{headers:{Authorization:`Bearer ${token}`},signal:AbortSignal.timeout(5000)});
      if(!response.ok)throw new Error(`Cannot load dataset registry (${response.status}). Check API and local token.`);
      setData(await response.json());
    }catch(error){setData(null);setStatus(error instanceof Error?error.message:"Request failed");}
    finally{setBusy(false);}
  }
  return <section className="workspace" aria-label="External research datasets">
    <p className="eyebrow">EXTERNAL RESEARCH DATA</p><h2>Dataset library</h2>
    <p className="muted">Detection-development images and geographic field-data previews. Tank inlet estimates use your measured calibration. Loading this library makes no remote dataset requests.</p>
    <label>Local token <input type="password" value={token} onChange={e=>setToken(e.target.value)} autoComplete="off" style={{padding:10,margin:10}}/></label>
    <button disabled={busy||!token} onClick={()=>void load()}>Load library</button>
    <p role="status">{busy?"Loading local registry…":status}</p>
    {data?.catalog.map(source=><div key={source.id} style={{margin:"22px 0"}}>
      <h3><a href={source.url} target="_blank" rel="noreferrer">{source.name}</a></h3>
      <p>{source.purpose} · {source.account_required?"Account required":"Public access"}</p>
      <p className="muted">{source.limitations}</p>
      {data.imports.filter(row=>row.dataset_id===source.id).map(row=><details key={row.id}>
        <summary>Imported {new Date(row.imported_at).toLocaleString()} · {row.id}</summary>
        <pre style={{overflowX:"auto",maxHeight:300}}>{JSON.stringify(row.summary,null,2)}</pre>
      </details>)}
      {!data.imports.some(row=>row.dataset_id===source.id)&&<p>No local import yet.</p>}
    </div>)}
  </section>;
}
