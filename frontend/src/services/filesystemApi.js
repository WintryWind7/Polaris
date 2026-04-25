import axios from 'axios'

const api = axios.create({
    baseURL: '/api/filesystem',
    timeout: 10000
})

export default {
    listDir(path = '') {
        return api.get('/list-dir', { params: { path } }).then(res => res.data)
    }
}
