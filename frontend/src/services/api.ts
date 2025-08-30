import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
})

export type RunCreate = { topic: string; language: string; chapter_count: number }
export type RunCreated = { id: string }
export type RunStatus = { id: string; status: string; error?: string | null; result?: any; updated_at?: number }

export const postRun = async (payload: RunCreate) => {
  const { data } = await api.post<RunCreated>('/api/v1/runs', payload)
  return data
}

export const getRunStatus = async (id: string) => {
  const { data } = await api.get<RunStatus>(`/api/v1/runs/${id}`)
  return data
}

export const openRunStream = (id: string): EventSource => {
  const base = api.defaults.baseURL?.replace(/\/$/, '') || ''
  return new EventSource(`${base}/api/v1/runs/${id}/stream`)
}

// KG Graph types and API
export type KgNode = { id: string; label?: string; type?: string; properties?: Record<string, any> }
export type KgEdge = { id?: string; source: string; target: string; label?: string; type?: string; properties?: Record<string, any> }
export type KgGraph = { nodes: KgNode[]; edges: KgEdge[] }

export const getKgSection = async (sectionId: string) => {
  const { data } = await api.get<KgGraph>(`/api/v1/kg/sections/${sectionId}`)
  return data
}

export const getKgBook = async (bookId: string) => {
  const { data } = await api.get<KgGraph>(`/api/v1/kg/books/${bookId}`)
  return data
}

export const getKnowledgeGraph = async (bookId?: string, sectionId?: string) => {
  if (bookId) {
    // 优先使用整本书图谱
    return await getKgBook(bookId);
  } else if (sectionId) {
    // 备选：使用小节图谱
    return await getKgSection(sectionId);
  }
  throw new Error('Neither bookId nor sectionId provided');
}

