import { createRouter, createWebHistory } from 'vue-router';
import Home from '../views/Home.vue';
import RunDetail from '../views/RunDetail.vue';
const routes = [
    { path: '/', name: 'home', component: Home },
    { path: '/runs/:id', name: 'run-detail', component: RunDetail, props: true }
];
const router = createRouter({
    history: createWebHistory(),
    routes
});
export default router;
