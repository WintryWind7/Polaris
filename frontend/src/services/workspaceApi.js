import axios from 'axios'

const api = axios.create({
    baseURL: '/api/workspaces',
    timeout: 10000
})

export default {
    getWorkspaces() {
        return api.get('').then(res => res.data)
    },
    createWorkspace(data) {
        return api.post('', data).then(res => res.data)
    },
    getWorkspace(id) {
        return api.get(`/${id}`).then(res => res.data)
    },
    updateWorkspace(id, data) {
        return api.put(`/${id}`, data).then(res => res.data)
    },
    deleteWorkspace(id) {
        return api.delete(`/${id}`).then(res => res.data)
    },
    getWorkspaceSessions(id) {
        return api.get(`/${id}/sessions`).then(res => res.data)
    }
}
