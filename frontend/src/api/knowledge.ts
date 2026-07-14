import { authFetch } from "./http";

export interface KnowledgeUpload {
  upload_id: string;
  city: string;
  source: string;
  chunk_count: number;
  created_at: string;
}

// 上传一篇攻略
export async function uploadKnowledge(
    city: string,
    source:string,
    content:string,
): Promise<{ upload_id: string;chunk_count:number}> {
    const resp = await authFetch("/api/knowledge",{
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body:JSON.stringify({city,source,content})
    });
    if (!resp.ok) {
        const err = await resp.json().catch(()=> ({ detail:resp.statusText}))
        throw new Error(err.detail || "上传失败")
    }
    return resp.json()
}

// 列出我的所有上传
export async function listKnowledge():Promise<KnowledgeUpload[]> {
    const resp = await authFetch("/api/knowledge")
    if (!resp.ok) return []
    return resp.json()
}

// 删除
export async function deleteKnowledge(uploadId:string):Promise<void>{
    const resp = await authFetch(`/api/knowledge/${uploadId}`,{method: "DELETE"})
    if (!resp.ok) throw new Error("删除失败");
}