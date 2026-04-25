/**
 * 系统 API 服务
 */
import axios from 'axios'

const API_BASE = '/api/system'

export default {
  /**
   * 打开系统文件夹选择对话框
   */
  async selectFolder() {
    const { data } = await axios.post(`${API_BASE}/select-folder`)
    return data
  }
}
