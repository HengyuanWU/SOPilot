import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
})

export type RunCreate = { 
  topic: string; 
  language: string; 
  chapter_count: number;
  workflow_id?: string;
  workflow_params?: Record<string, any>;
}
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

// Workflow types and API
export type WorkflowMetadata = {
  id: string;
  name: string;
  description: string;
  version: string;
  tags: string[];
  input_schema: Record<string, any>;
  ui_schema?: Record<string, any>;
}

export type WorkflowSchema = {
  input_schema: Record<string, any>;
  ui_schema?: Record<string, any>;
}

export const getWorkflows = async (): Promise<WorkflowMetadata[]> => {
  const { data } = await api.get<WorkflowMetadata[]>('/api/v1/workflows')
  return data
}

export const getWorkflowDetail = async (workflowId: string): Promise<WorkflowMetadata> => {
  const { data } = await api.get<WorkflowMetadata>(`/api/v1/workflows/${workflowId}`)
  return data
}

export const getWorkflowSchema = async (workflowId: string): Promise<WorkflowSchema> => {
  const { data } = await api.get<WorkflowSchema>(`/api/v1/workflows/${workflowId}/schema`)
  return data
}

// Artifacts types and API
export type ArtifactFile = {
  name: string;
  size: number;
  modified: number;
  type: string;
}

export const getRunArtifacts = async (runId: string): Promise<ArtifactFile[]> => {
  const { data } = await api.get<ArtifactFile[]>(`/api/v1/runs/${runId}/artifacts`)
  return data
}

export const downloadRunFile = (runId: string, fileName: string): string => {
  const base = api.defaults.baseURL?.replace(/\/$/, '') || ''
  return `${base}/api/v1/runs/${runId}/download?file=${encodeURIComponent(fileName)}`
}

export const downloadRunArchive = (runId: string): string => {
  const base = api.defaults.baseURL?.replace(/\/$/, '') || ''
  return `${base}/api/v1/runs/${runId}/archive.zip`
}

