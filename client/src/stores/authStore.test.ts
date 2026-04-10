import axios from "axios";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "./authStore";

vi.mock("axios", () => ({
    default: {
        post: vi.fn(),
    },
}));

function makeAccessToken(expirationSecondsFromNow = 3600) {
    const payload = {
        exp: Math.floor(Date.now() / 1000) + expirationSecondsFromNow,
    };
    const encodedPayload = window.btoa(JSON.stringify(payload)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
    return `header.${encodedPayload}.signature`;
}

function setVisibilityState(state: DocumentVisibilityState) {
    Object.defineProperty(document, "visibilityState", {
        configurable: true,
        value: state,
    });
}

function installCookieJar() {
    const cookies = new Map<string, string>();
    Object.defineProperty(document, "cookie", {
        configurable: true,
        get: () => {
            return Array.from(cookies.entries())
                .map(([name, value]) => `${name}=${value}`)
                .join("; ");
        },
        set: (cookie: string) => {
            const [pair, ...options] = cookie.split(";").map((part) => part.trim());
            const [name, value] = pair.split("=", 2);
            const expiresNow = options.some((option) => option.toLowerCase() === "max-age=0") || value === "";
            if (expiresNow) {
                cookies.delete(name);
                return;
            }
            cookies.set(name, value);
        },
    });
}

describe("authStore", () => {
    beforeEach(() => {
        setActivePinia(createPinia());
        vi.mocked(axios.post).mockReset();
        installCookieJar();
        setVisibilityState("visible");
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it("bootstraps access token state from the backend response", async () => {
        const accessToken = makeAccessToken();
        document.cookie = "galaxy_refresh_csrf_token=csrf-token";
        vi.mocked(axios.post).mockResolvedValue({
            data: {
                access_token: accessToken,
                actor_user: null,
                auth_source: "galaxy_token",
                authenticated: true,
                current_history_id: "encoded-history",
                user: null,
            },
        });

        const authStore = useAuthStore();
        await authStore.bootstrap();

        expect(axios.post).toHaveBeenCalledWith("/auth/bootstrap", null, {
            headers: { "X-CSRF-Token": "csrf-token" },
        });
        expect(authStore.accessToken).toBe(accessToken);
        expect(authStore.isAuthenticated).toBe(true);
        expect(authStore.currentHistoryId).toBe("encoded-history");
    });

    it("keeps anonymous bootstrap responses anonymous without scheduling refresh", async () => {
        document.cookie = "galaxy_refresh_csrf_token=csrf-token";
        vi.mocked(axios.post).mockResolvedValue({
            data: {
                access_token: null,
                actor_user: null,
                auth_source: "anonymous",
                authenticated: false,
                current_history_id: null,
                user: null,
            },
        });

        const authStore = useAuthStore();
        await authStore.bootstrap();

        expect(axios.post).toHaveBeenCalledWith("/auth/bootstrap", null, {
            headers: { "X-CSRF-Token": "csrf-token" },
        });
        expect(authStore.accessToken).toBeNull();
        expect(authStore.isAuthenticated).toBe(false);
        expect(authStore.currentHistoryId).toBeNull();
        expect(authStore.bootstrapStatus).toBe("ready");
        expect(authStore.bootstrapError).toBeNull();
    });

    it("surfaces bootstrap failures and clears auth state", async () => {
        document.cookie = "galaxy_refresh_csrf_token=csrf-token";
        vi.mocked(axios.post).mockRejectedValue(new Error("bootstrap failed"));

        const authStore = useAuthStore();
        authStore.accessToken = makeAccessToken();
        authStore.authSource = "galaxy_token";
        authStore.currentHistoryId = "encoded-history";

        await expect(authStore.bootstrap()).rejects.toThrow("bootstrap failed");

        expect(authStore.bootstrapStatus).toBe("idle");
        expect(authStore.bootstrapError).toBeNull();
        expect(authStore.accessToken).toBeNull();
        expect(authStore.currentHistoryId).toBeNull();
        expect(authStore.isAuthenticated).toBe(false);
    });

    it("sends the refresh csrf token on all auth endpoints", async () => {
        const accessToken = makeAccessToken();
        document.cookie = "galaxy_refresh_csrf_token=csrf-token";
        vi.mocked(axios.post).mockResolvedValue({
            data: {
                access_token: accessToken,
                actor_user: null,
                auth_source: "galaxy_token",
                authenticated: true,
                current_history_id: null,
                user: null,
            },
        });

        const authStore = useAuthStore();
        await authStore.login({
            login: "user",
            password: "password",
            redirect: "/user",
        });
        await authStore.register({
            email: "user@example.org",
            username: "user",
            password: "password",
            confirm: "password",
        });
        await authStore.bootstrap();
        await authStore.refresh();
        await authStore.logout();

        expect(axios.post).toHaveBeenNthCalledWith(
            1,
            "/auth/login",
            {
                login: "user",
                password: "password",
                redirect: "/user",
            },
            {
                headers: { "X-CSRF-Token": "csrf-token" },
            },
        );
        expect(axios.post).toHaveBeenNthCalledWith(
            2,
            "/auth/register",
            {
                email: "user@example.org",
                username: "user",
                password: "password",
                confirm: "password",
            },
            {
                headers: { "X-CSRF-Token": "csrf-token" },
            },
        );
        expect(axios.post).toHaveBeenNthCalledWith(3, "/auth/bootstrap", null, {
            headers: { "X-CSRF-Token": "csrf-token" },
        });
        expect(axios.post).toHaveBeenNthCalledWith(4, "/auth/refresh", null, {
            headers: { "X-CSRF-Token": "csrf-token" },
        });
        expect(axios.post).toHaveBeenNthCalledWith(
            5,
            "/auth/logout",
            null,
            expect.objectContaining({
                headers: { "X-CSRF-Token": "csrf-token" },
                params: {
                    logout_all: false,
                },
            }),
        );
    });

    it("returns logout_all when requested", async () => {
        document.cookie = "galaxy_refresh_csrf_token=csrf-token";
        vi.mocked(axios.post).mockResolvedValue({
            data: {
                message: "Success.",
            },
        });

        const authStore = useAuthStore();
        const response = await authStore.logout(true);

        expect(axios.post).toHaveBeenCalledWith(
            "/auth/logout",
            null,
            {
                headers: { "X-CSRF-Token": "csrf-token" },
                params: {
                    logout_all: true,
                },
            },
        );
        expect(response.logout_all).toBe(true);
    });

    it("deduplicates bootstrap calls while the first request is in flight", async () => {
        const accessToken = makeAccessToken();
        document.cookie = "galaxy_refresh_csrf_token=csrf-token";
        vi.mocked(axios.post).mockResolvedValue({
            data: {
                access_token: accessToken,
                actor_user: null,
                auth_source: "galaxy_token",
                authenticated: true,
                current_history_id: null,
                user: null,
            },
        });

        const authStore = useAuthStore();
        const first = authStore.ensureBootstrap();
        const second = authStore.ensureBootstrap();
        await Promise.all([first, second]);

        expect(axios.post).toHaveBeenCalledTimes(1);
        expect(authStore.accessToken).toBe(accessToken);
    });

    it("logs in and hydrates user state from the backend response", async () => {
        const accessToken = makeAccessToken();
        document.cookie = "galaxy_refresh_csrf_token=csrf-token";
        vi.mocked(axios.post).mockResolvedValue({
            data: {
                access_token: accessToken,
                actor_user: {
                    email: "actor@example.org",
                    id: "encoded-actor",
                    username: "actor",
                },
                auth_source: "galaxy_token",
                authenticated: true,
                current_history_id: "encoded-history",
                user: {
                    email: "user@example.org",
                    id: "encoded-user",
                    username: "user",
                },
            },
        });

        const authStore = useAuthStore();
        const response = await authStore.login({
            login: "user",
            password: "password",
            redirect: "/user",
        });

        expect(axios.post).toHaveBeenCalledTimes(1);
        expect(axios.post.mock.calls[0]?.[0]).toBe("/auth/login");
        expect(axios.post.mock.calls[0]?.[1]).toEqual({
            login: "user",
            password: "password",
            redirect: "/user",
        });
        expect(response.access_token).toBe(accessToken);
        expect(authStore.accessToken).toBe(accessToken);
        expect(authStore.effectiveUser?.id).toBe("encoded-user");
        expect(authStore.actorUser?.id).toBe("encoded-actor");
        expect(authStore.currentHistoryId).toBe("encoded-history");
    });

    it("rejects auth responses that return an error message", async () => {
        document.cookie = "galaxy_refresh_csrf_token=csrf-token";
        vi.mocked(axios.post).mockResolvedValue({
            data: {
                err_msg: "Login failed.",
            },
        });

        const authStore = useAuthStore();

        await expect(
            authStore.login({
                login: "user",
                password: "password",
                redirect: "/user",
            }),
        ).rejects.toThrow("Login failed.");
        await expect(
            authStore.register({
                email: "user@example.org",
                username: "user",
                password: "password",
                confirm: "password",
            }),
        ).rejects.toThrow("Login failed.");
    });

    it("clears auth state on logout", async () => {
        document.cookie = "galaxy_refresh_csrf_token=csrf-token";
        vi.mocked(axios.post).mockResolvedValue({
            data: {
                message: "Success.",
            },
        });

        const authStore = useAuthStore();
        authStore.accessToken = makeAccessToken();
        authStore.authSource = "galaxy_token";

        await authStore.logout();

        expect(axios.post).toHaveBeenCalledWith(
            "/auth/logout",
            null,
            expect.objectContaining({
                params: {
                    logout_all: false,
                },
            }),
        );
        expect(authStore.accessToken).toBeNull();
        expect(authStore.isAuthenticated).toBe(false);
        expect(authStore.authSource).toBeNull();
    });

    it("refreshes proactively only when the token is near expiry and the tab is visible", async () => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date("2024-01-01T00:00:00Z"));
        setVisibilityState("visible");
        document.cookie = "galaxy_refresh_csrf_token=csrf-token";
        const bootstrapAccessToken = makeAccessToken(90);
        const refreshedAccessToken = makeAccessToken(180);
        vi.mocked(axios.post)
            .mockResolvedValueOnce({
                data: {
                    access_token: bootstrapAccessToken,
                    actor_user: null,
                    auth_source: "galaxy_token",
                    authenticated: true,
                    current_history_id: null,
                    user: null,
                },
            })
            .mockResolvedValueOnce({
                data: {
                    access_token: refreshedAccessToken,
                    actor_user: null,
                    auth_source: "galaxy_token",
                    authenticated: true,
                    current_history_id: null,
                    user: null,
                },
            });

        const authStore = useAuthStore();
        await authStore.bootstrap();

        expect(axios.post).toHaveBeenCalledTimes(1);
        await vi.advanceTimersByTimeAsync(59_000);
        expect(axios.post).toHaveBeenCalledTimes(1);
        await vi.advanceTimersByTimeAsync(1_000);
        await Promise.resolve();

        expect(axios.post).toHaveBeenCalledTimes(2);
        expect(axios.post).toHaveBeenNthCalledWith(2, "/auth/refresh", null, {
            headers: { "X-CSRF-Token": "csrf-token" },
        });
        expect(authStore.accessToken).toBe(refreshedAccessToken);
    });

    it("does not refresh when the token is still far from expiry", async () => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date("2024-01-01T00:00:00Z"));
        setVisibilityState("visible");
        document.cookie = "galaxy_refresh_csrf_token=csrf-token";
        vi.mocked(axios.post).mockResolvedValue({
            data: {
                access_token: makeAccessToken(300),
                actor_user: null,
                auth_source: "galaxy_token",
                authenticated: true,
                current_history_id: null,
                user: null,
            },
        });

        const authStore = useAuthStore();
        await authStore.bootstrap();
        await vi.advanceTimersByTimeAsync(60_000);

        expect(axios.post).toHaveBeenCalledTimes(1);
    });

    it("does not refresh proactively while the tab is hidden", async () => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date("2024-01-01T00:00:00Z"));
        setVisibilityState("hidden");
        document.cookie = "galaxy_refresh_csrf_token=csrf-token";
        vi.mocked(axios.post).mockResolvedValue({
            data: {
                access_token: makeAccessToken(90),
                actor_user: null,
                auth_source: "galaxy_token",
                authenticated: true,
                current_history_id: null,
                user: null,
            },
        });

        const authStore = useAuthStore();
        await authStore.bootstrap();
        await vi.advanceTimersByTimeAsync(60_000);

        expect(axios.post).toHaveBeenCalledTimes(1);
        expect(authStore.accessToken).toBeTruthy();
    });

    it("does not refresh when there is no active token", async () => {
        const authStore = useAuthStore();
        await authStore.maybeRefresh();

        expect(axios.post).not.toHaveBeenCalled();
    });

    it("tracks impersonation when actor and effective user differ", async () => {
        document.cookie = "galaxy_refresh_csrf_token=csrf-token";
        vi.mocked(axios.post).mockResolvedValue({
            data: {
                access_token: makeAccessToken(),
                actor_user: {
                    email: "actor@example.org",
                    id: "encoded-actor",
                    username: "actor",
                },
                auth_source: "galaxy_token",
                authenticated: true,
                current_history_id: null,
                user: {
                    email: "user@example.org",
                    id: "encoded-user",
                    username: "user",
                },
            },
        });

        const authStore = useAuthStore();
        await authStore.bootstrap();

        expect(authStore.isImpersonating).toBe(true);
    });
});
