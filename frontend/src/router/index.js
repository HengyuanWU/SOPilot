import { createRouter, createWebHistory } from 'vue-router';
import Home from '../views/Home.vue';
import RunDetail from '../views/RunDetail.vue';
import PromptStudio from '../views/PromptStudio.vue';
import KnowledgeBase from '../views/KnowledgeBase.vue';
const routes = [
    { path: '/', name: 'home', component: Home },
    { path: '/runs/:id', name: 'run-detail', component: RunDetail, props: true },
    { path: '/prompts', name: 'prompt-studio', component: PromptStudio },
    { path: '/knowledge', name: 'knowledge-base', component: KnowledgeBase }
];
const router = createRouter({
    history: createWebHistory(),
    routes
});
export default router;
