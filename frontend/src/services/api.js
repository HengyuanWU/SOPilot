import axios from 'axios';

const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
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
    } else if (sectionId) {
        // 备选：使用小节图谱
        return await getKgSection(sectionId);
    }
    throw new Error('Neither bookId nor sectionId provided');
}; 