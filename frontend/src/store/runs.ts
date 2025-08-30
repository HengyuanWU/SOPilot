import { defineStore } from 'pinia'
import { postRun, getRunStatus, openRunStream, type RunCreate, type RunStatus } from '../services/api'

type RunState = {
  currentId: string | null
  status: RunStatus | null
  logs: string[]
}

export const useRunsStore = defineStore('runs', {
  state: (): RunState => ({ currentId: null, status: null, logs: [] }),
  actions: {
    async createRun(payload: RunCreate) {
      const created = await postRun(payload)
      this.currentId = created.id
      this.logs = []
      this.watchStream(created.id)
      return created
    },
    async fetchStatus(id: string) {
      this.status = await getRunStatus(id)
      return this.status
    },
    watchStream(id: string) {
      const es = openRunStream(id)
      es.addEventListener('log', (e: MessageEvent) => {
        this.logs.push((e as MessageEvent).data)
      })
      es.addEventListener('end', () => {
        es.close()
      })
    }
  }
})

