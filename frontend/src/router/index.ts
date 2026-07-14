import { createRouter, createWebHistory } from "vue-router";
import { isLoggedIn } from "../lib/session";
import HomeView from "../views/HomeView.vue";
import AuthView from "../views/AuthView.vue";
import KnowledgeView from "../views/KnowledgeView.vue";


const routes = [
  { path: "/login", name: "login", component: AuthView },
  { path: "/",name:'home',component:HomeView,meta:{requiresAuth:true} },
  { path: "/knowledge", name: "knowledge", component: KnowledgeView, meta: { requiresAuth: true } }, 
];

const router = createRouter({
    history: createWebHistory(),
    routes
})

router.beforeEach((to)=> {
    if (to.meta.requiresAuth && !isLoggedIn()) {
        return {name:'login'}
    }
    if (to.name === 'login' && isLoggedIn()) {
        return {name:'home'}
    }
})

export default router