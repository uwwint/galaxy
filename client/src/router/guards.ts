import type { NavigationGuardNext, Route } from "vue-router";

import { useAuthStore } from "@/stores/authStore";

export async function requireAuth(to: Route, from: Route, next: NavigationGuardNext) {
    const authStore = useAuthStore();
    await authStore.ensureBootstrap().catch(() => undefined);

    if (!authStore.accessToken || !authStore.effectiveUser) {
        next({
            path: "/login/start",
            query: {
                redirect: to.fullPath,
            },
        });
        return;
    }
    next();
}
