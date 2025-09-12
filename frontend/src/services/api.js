import axios from 'axios';
export const api = axios.create({
    baseURL: ''
});
export const postRun = async (payload) => {
    const { data } = await api.post('/api/v1/runs', payload);
    return data;
};
export const getRunStatus = async (id) => {
    const { data } = await api.get(`/api/v1/runs/${id}`);
    return data;
};
export const openRunStream = (id) => {
    const base = api.defaults.baseURL?.replace(/\/$/, '') || '';
    return new EventSource(`${base}/api/v1/runs/${id}/stream`);
};
export const getKgSection = async (sectionId) => {
    const { data } = await api.get(`/api/v1/kg/sections/${sectionId}`);
    return data;
};
export const getKgBook = async (bookId) => {
    const { data } = await api.get(`/api/v1/kg/books/${bookId}`);
    return data;
};
export const getKnowledgeGraph = async (bookId, sectionId) => {
    if (bookId) {
        // 优先使用整本书图谱
        return await getKgBook(bookId);
    }
    else if (sectionId) {
        // 备选：使用小节图谱
        return await getKgSection(sectionId);
    }
    throw new Error('Neither bookId nor sectionId provided');
};
export const getWorkflows = async () => {
    const { data } = await api.get('/api/v1/workflows');
    return data;
};
export const getWorkflowDetail = async (workflowId) => {
    const { data } = await api.get(`/api/v1/workflows/${workflowId}`);
    return data;
};
export const getWorkflowSchema = async (workflowId) => {
    const { data } = await api.get(`/api/v1/workflows/${workflowId}/schema`);
    return data;
};
export const getRunArtifacts = async (runId) => {
    const { data } = await api.get(`/api/v1/runs/${runId}/artifacts`);
    return data;
};
export const downloadRunFile = (runId, fileName) => {
    const base = api.defaults.baseURL?.replace(/\/$/, '') || '';
    return `${base}/api/v1/runs/${runId}/download?file=${encodeURIComponent(fileName)}`;
};
export const downloadRunArchive = (runId) => {
    const base = api.defaults.baseURL?.replace(/\/$/, '') || '';
    return `${base}/api/v1/runs/${runId}/archive.zip`;
};
