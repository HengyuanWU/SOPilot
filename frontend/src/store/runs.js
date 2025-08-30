import { defineStore } from 'pinia';
import { postRun, getRunStatus, openRunStream } from '../services/api';
export const useRunsStore = defineStore('runs', {
    state: () => ({ currentId: null, status: null, logs: [] }),
    actions: {
        async createRun(payload) {
            const created = await postRun(payload);
            this.currentId = created.id;
            this.logs = [];
            this.watchStream(created.id);
            return created;
        },
        async fetchStatus(id) {
            this.status = await getRunStatus(id);
            return this.status;
        },
        watchStream(id) {
            const es = openRunStream(id);
            es.addEventListener('log', (e) => {
                this.logs.push(e.data);
            });
            es.addEventListener('end', () => {
                es.close();
            });
        }
    }
});
