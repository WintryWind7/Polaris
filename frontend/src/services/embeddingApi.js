/**
 * Embedding API 服务
 */
import axios from 'axios'

const API_BASE = 'http://127.0.0.1:6547/api/embeddings'

export default {
  /**
   * 获取所有 Embeddings
   */
  async getEmbeddings() {
    const { data } = await axios.get(API_BASE)
    return data
  },

  /**
   * 获取指定 Embedding
   */
  async getEmbedding(embeddingId) {
    const { data } = await axios.get(`${API_BASE}/${embeddingId}`)
    return data
  },

  /**
   * 添加 Embedding
   */
  async addEmbedding(payload) {
    const { data } = await axios.post(API_BASE, payload)
    return data
  },

  /**
   * 更新 Embedding
   */
  async updateEmbedding(embeddingId, payload) {
    const { data } = await axios.put(`${API_BASE}/${embeddingId}`, payload)
    return data
  },

  /**
   * 删除 Embedding
   */
  async deleteEmbedding(embeddingId) {
    const { data } = await axios.delete(`${API_BASE}/${embeddingId}`)
    return data
  },

  /**
   * 扫描本地模型
   */
  async scanLocalModels() {
    const { data } = await axios.get(`${API_BASE}/scan/local`)
    return data
  },

  /**
   * 获取模型目录信息
   */
  async getDirectory() {
    const { data } = await axios.get(`${API_BASE}/directory/info`)
    return data
  },

  /**
   * 浏览目录
   */
  async browseDirectory(path = '') {
    const { data } = await axios.post(`${API_BASE}/directory/browse`, null, {
      params: { path }
    })
    return data
  },

  /**
   * 重建向量数据库
   */
  async rebuildEmbeddings() {
    const { data } = await axios.post(`${API_BASE}/rebuild`)
    return data
  },

  /**
   * 检查兼容性
   */
  async checkCompatibility() {
    const { data } = await axios.get(`${API_BASE}/compatibility`)
    return data
  }
}
