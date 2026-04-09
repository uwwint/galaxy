import axios from "axios";
import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { withPrefix } from "@/utils/redirect";

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
        accessToken.value = null;
        accessTokenExpiresAt.value = null;
        authSource.value = null;
        effectiveUser.value = null;
        actorUser.value = null;
        currentHistoryId.value = null;
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
        if (payload.access_token) {
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
        const response = await axios.post(withPrefix(path), payload, params ? { params } : undefined);
        if (response.data?.err_msg) {
            throw new Error(response.data.err_msg);
        }
        return response.data as T;
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

    function hasActiveAuthToken() {
        return accessToken.value !== null;
    }

    return {
        accessToken,
        authSource,
        actorUser,
        bootstrapError,
        bootstrapStatus,
        currentHistoryId,
        effectiveUser,
        hasActiveAuthToken,
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
