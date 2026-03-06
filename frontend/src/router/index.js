import { createRouter, createWebHistory } from 'vue-router'
import DashboardLayout from '../layouts/DashboardLayout.vue'
import HomeView from '../views/HomeView.vue'
import SettingsView from '../views/SettingsView.vue'
import LogsView from '../views/LogsView.vue'
import ChatView from '../views/ChatView.vue'
import SystemSettings from '../views/SystemSettings.vue'

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes: [
        {
            path: '/',
            component: DashboardLayout,
            children: [
                {
                    path: '',
                    name: 'home',
                    component: HomeView
                },
                {
                    path: 'chat',
                    name: 'chat',
                    component: ChatView
                },
                {
                    path: 'settings',
                    name: 'settings',
                    component: SettingsView
                },
                {
                    path: 'logs',
                    name: 'logs',
                    component: LogsView
                },
                {
                    path: 'system',
                    name: 'system',
                    component: SystemSettings
                }
            ]
        }
    ]
})

export default router
