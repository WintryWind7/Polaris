import axios from 'axios'

const api = axios.create({
    baseURL: '/api/providers',
    timeout: 10000
})

export default {
    // 获取所有 Providers
    getProviders() {
        // 明确使用空字符串，避免末尾带杠引发的潜在 404/307 问题
        return api.get('').then(res => res.data)
    },

    // 添加 Provider
    addProvider(data) {
        return api.post('', data).then(res => res.data)
    },

    // 更新 Provider
    updateProvider(providerId, data) {
        return api.put(`/${providerId}`, data).then(res => res.data)
    },

    // 删除 Provider
    deleteProvider(providerId) {
        return api.delete(`/${providerId}`).then(res => res.data)
    }
}
