import axios from 'axios'

const api = axios.create({
    baseURL: '/api/config',
    timeout: 10000
})

export default {
    // 获取全局配置
    getConfig() {
        return api.get('').then(res => res.data)
    },

    // 更新全局配置
    updateConfig(updates) {
        return api.put('', updates).then(res => res.data)
    }
}
