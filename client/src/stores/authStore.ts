import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { GalaxyApi } from "@/api";
import { getGalaxyInstance } from "@/app";
import { User } from "@/app/user";

interface SerializedUser {
    id: string;
    email: string;
    username: string;
}

interface BrowserAuthPayload {
    access_token: string | null;
    actor_user: SerializedUser | null;
    auth_source: string | null;
    authenticated: boolean;
    current_history_id: string | null;
    expired_user?: string;
    message?: string;
    redirect?: string;
    status?: string;
    user: SerializedUser | null;
}

type BrowserAuthResponse = BrowserAuthPayload & {
    err_msg?: string;
};

interface LoginPayload {
    login: string;
    password: string | null;
    redirect?: string | null;
}

interface RegisterPayload {
    email: string | null;
    username: string | null;
    password: string | null;
    confirm: string | null;
    subscribe?: boolean | null;
}

const REFRESH_SKEW_MS = 30_000;
const AUTH_REFRESH_CSRF_COOKIE_NAME = "galaxy_refresh_csrf_token";

function decodeBase64Url(value: string): string {
    const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
    const padding = "=".repeat((4 - (normalized.length % 4)) % 4);
    return window.atob(normalized + padding);
}

function tokenExpiresAt(accessToken: string): number | null {
    try {
        const [, payload] = accessToken.split(".");
        if (!payload) {
            return null;
        }
        const decoded = JSON.parse(decodeBase64Url(payload)) as { exp?: unknown };
        return typeof decoded.exp === "number" ? decoded.exp * 1000 : null;
    } catch {
        return null;
    }
}

function syncGalaxyUser(user: SerializedUser | null) {
    const galaxy = getGalaxyInstance();
    if (!galaxy) {
        return;
    }
    galaxy.user = new User(user ?? {});
}

function readCookieValue(name: string): string | null {
    if (typeof document === "undefined") {
        return null;
    }
    const escapedName = name.replace(/([.*+?^${}()|[\]\\])/g, "\\$1");
    const match = document.cookie.match(new RegExp(`(?:^|; )${escapedName}=([^;]*)`));
    return match ? decodeURIComponent(match[1]) : null;
}

export const useAuthStore = defineStore("authStore", () => {
    const accessToken = ref<string | null>(null);
    const accessTokenExpiresAt = ref<number | null>(null);
    const authSource = ref<string | null>(null);
    const effectiveUser = ref<SerializedUser | null>(null);
    const actorUser = ref<SerializedUser | null>(null);
    const currentHistoryId = ref<string | null>(null);
    const bootstrapStatus = ref<"idle" | "loading" | "ready" | "error">("idle");
    const bootstrapError = ref<string | null>(null);

    let refreshTimer: number | null = null;
    let refreshPromise: Promise<BrowserAuthPayload> | null = null;
    let bootstrapPromise: Promise<BrowserAuthPayload> | null = null;
    let refreshListenersBound = false;

    const isAuthenticated = computed(() => Boolean(accessToken.value));
    const isImpersonating = computed(() => {
        return (
            actorUser.value !== null &&
            effectiveUser.value !== null &&
            actorUser.value.id !== effectiveUser.value.id
        );
    });

    function clearRefreshTimer() {
        if (refreshTimer !== null) {
            window.clearTimeout(refreshTimer);
            refreshTimer = null;
        }
    }

    function resetBootstrapState() {
        bootstrapStatus.value = "idle";
        bootstrapError.value = null;
    }

    function clearAuthState() {
        const galaxy = getGalaxyInstance();
        galaxy?.user?.clearSessionStorage();
        accessToken.value = null;
        accessTokenExpiresAt.value = null;
        authSource.value = null;
        effectiveUser.value = null;
        actorUser.value = null;
        currentHistoryId.value = null;
        syncGalaxyUser(null);
        clearRefreshTimer();
        resetBootstrapState();
    }

    function bindRefreshListeners() {
        if (refreshListenersBound || typeof window === "undefined") {
            return;
        }
        const handleRefreshSignal = () => {
            if (document.visibilityState === "visible" && accessTokenExpiresAt.value !== null) {
                void maybeRefresh();
            }
        };
        window.addEventListener("focus", handleRefreshSignal);
        document.addEventListener("visibilitychange", handleRefreshSignal);
        refreshListenersBound = true;
    }

    function scheduleRefresh() {
        clearRefreshTimer();
        bindRefreshListeners();
        if (accessToken.value === null || accessTokenExpiresAt.value === null) {
            return;
        }
        const delay = accessTokenExpiresAt.value - Date.now() - REFRESH_SKEW_MS;
        if (delay <= 0) {
            void maybeRefresh();
            return;
        }
        refreshTimer = window.setTimeout(() => {
            void maybeRefresh();
        }, delay);
    }

    function applyBootstrapPayload(payload: BrowserAuthPayload) {
        accessToken.value = payload.access_token;
        accessTokenExpiresAt.value = payload.access_token ? tokenExpiresAt(payload.access_token) : null;
        authSource.value = payload.auth_source;
        effectiveUser.value = payload.user;
        actorUser.value = payload.actor_user;
        currentHistoryId.value = payload.current_history_id;
        syncGalaxyUser(payload.user);
        if (payload.authenticated && payload.access_token) {
            scheduleRefresh();
        } else {
            clearRefreshTimer();
        }
        bootstrapStatus.value = "ready";
        bootstrapError.value = null;
        return payload;
    }

    async function postAuthEndpoint<T>(
        path: string,
        payload: Record<string, unknown> | null = null,
        params: Record<string, unknown> | null = null,
    ): Promise<T> {
        const csrfToken = readCookieValue(AUTH_REFRESH_CSRF_COOKIE_NAME);
        const config = {
            ...(params ? { params } : {}),
            ...(csrfToken ? { headers: { "X-CSRF-Token": csrfToken } } : {}),
        };
        const { data, error } = await GalaxyApi().POST(path as never, {
            body: payload,
            ...(Object.keys(config).length ? config : {}),
        });
        if (error) {
            throw error;
        }
        if (data?.err_msg) {
            throw new Error(data.err_msg);
        }
        return data as T;
    }

    async function bootstrap(): Promise<BrowserAuthPayload> {
        bootstrapStatus.value = "loading";
        try {
            const payload = await postAuthEndpoint<BrowserAuthResponse>("/auth/bootstrap");
            return applyBootstrapPayload(payload);
        } catch (error) {
            bootstrapStatus.value = "error";
            bootstrapError.value = error instanceof Error ? error.message : "Login completion failed.";
            clearAuthState();
            throw error;
        }
    }

    async function ensureBootstrap(): Promise<BrowserAuthPayload> {
        if (bootstrapPromise) {
            return bootstrapPromise;
        }
        bootstrapPromise = bootstrap();
        try {
            return await bootstrapPromise;
        } finally {
            bootstrapPromise = null;
        }
    }

    async function refresh(): Promise<BrowserAuthPayload> {
        if (refreshPromise) {
            return refreshPromise;
        }
        refreshPromise = (async () => {
            const payload = await postAuthEndpoint<BrowserAuthResponse>("/auth/refresh");
            return applyBootstrapPayload(payload);
        })();
        try {
            return await refreshPromise;
        } finally {
            refreshPromise = null;
        }
    }

    async function maybeRefresh() {
        if (accessToken.value === null || accessTokenExpiresAt.value === null) {
            return;
        }
        if (document.visibilityState !== "visible") {
            return;
        }
        if (accessTokenExpiresAt.value - Date.now() > REFRESH_SKEW_MS) {
            return;
        }
        await refresh();
    }

    async function login(payload: LoginPayload): Promise<BrowserAuthResponse> {
        const response = await postAuthEndpoint<BrowserAuthResponse>("/auth/login", payload);
        if (response.access_token && typeof response.access_token === "string") {
            applyBootstrapPayload(response);
        }
        return response;
    }

    async function register(payload: RegisterPayload): Promise<BrowserAuthResponse> {
        const response = await postAuthEndpoint<BrowserAuthResponse>("/auth/register", payload);
        if (response.access_token && typeof response.access_token === "string") {
            applyBootstrapPayload(response);
        }
        return response;
    }

    async function logout(logoutAll = false): Promise<BrowserAuthResponse> {
        const response = await postAuthEndpoint<BrowserAuthResponse>("/auth/logout", null, {
            logout_all: logoutAll,
        });
        clearAuthState();
        if (logoutAll) {
            return { ...response, logout_all: true };
        }
        return response;
    }

    return {
        accessToken,
        authSource,
        actorUser,
        bootstrapError,
        bootstrapStatus,
        currentHistoryId,
        effectiveUser,
        ensureBootstrap,
        isAuthenticated,
        isImpersonating,
        bootstrap,
        clearAuthState,
        login,
        logout,
        maybeRefresh,
        refresh,
        register,
    };
});
