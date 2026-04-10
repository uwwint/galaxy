import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HttpResponse, useServerMock } from "@/api/client/__mocks__";
import { useAuthStore } from "@/stores/authStore";

import { GalaxyApi } from "./index";

const { server, http } = useServerMock();

function makeAccessToken(expirationSecondsFromNow = 3600) {
    const payload = {
        exp: Math.floor(Date.now() / 1000) + expirationSecondsFromNow,
    };
    const encodedPayload = window.btoa(JSON.stringify(payload)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
    return `header.${encodedPayload}.signature`;
}

describe("GalaxyApi auth middleware", () => {
    beforeEach(() => {
        setActivePinia(createPinia());
        vi.restoreAllMocks();
        document.cookie = "galaxy_refresh_csrf_token=; Max-Age=0; path=/";
    });

    it("adds the bearer token to API requests", async () => {
        const authStore = useAuthStore();
        authStore.accessToken = "test-access-token";

        let authorizationHeader: string | null = null;
        server.use(
            http.get("/api/configuration", ({ request, response }) => {
                authorizationHeader = request.headers.get("Authorization");
                return response.untyped(HttpResponse.json({}));
            }),
        );

        await GalaxyApi().GET("/api/configuration");

        expect(authorizationHeader).toBe("Bearer test-access-token");
    });

    it("refreshes expired access tokens and retries the request when the refresh succeeds", async () => {
        const authStore = useAuthStore();
        authStore.accessToken = "expired-access-token";
        document.cookie = "galaxy_refresh_csrf_token=csrf-token";
        const refreshedAccessToken = makeAccessToken();
        const authorizationHeaders: Array<string | null> = [];
        let refreshHeader: string | null = null;
        let requestCount = 0;
        server.use(
            http.get("/api/configuration", ({ request, response }) => {
                authorizationHeaders.push(request.headers.get("Authorization"));
                requestCount += 1;
                if (requestCount === 1) {
                    return response("4XX").json({ err_msg: "Unauthorized" }, { status: 401 });
                }
                return response.untyped(HttpResponse.json({ ok: true }));
            }),
            http.post("/auth/refresh", ({ request, response }) => {
                refreshHeader = request.headers.get("X-CSRF-Token");
                return response.untyped(
                    HttpResponse.json({
                        access_token: refreshedAccessToken,
                        actor_user: null,
                        auth_source: "galaxy_token",
                        authenticated: true,
                        current_history_id: null,
                        user: null,
                    }),
                );
            }),
        );

        const { response } = await GalaxyApi().GET("/api/configuration");

        expect(response.status).toBe(200);
        expect(authorizationHeaders).toEqual(["Bearer expired-access-token", `Bearer ${refreshedAccessToken}`]);
        expect(refreshHeader).toBe("csrf-token");
        expect(authStore.accessToken).toBe(refreshedAccessToken);
    });

    it("returns the original 401 when the refresh token has expired", async () => {
        const authStore = useAuthStore();
        authStore.accessToken = "expired-access-token";
        document.cookie = "galaxy_refresh_csrf_token=csrf-token";
        let refreshCalls = 0;
        server.use(
            http.get("/api/configuration", ({ request, response }) => {
                expect(request.headers.get("Authorization")).toBe("Bearer expired-access-token");
                return response("4XX").json({ err_msg: "Unauthorized" }, { status: 401 });
            }),
            http.post("/auth/refresh", ({ response }) => {
                refreshCalls += 1;
                return response("4XX").json({ err_msg: "Refresh token expired" }, { status: 401 });
            }),
        );

        const { response } = await GalaxyApi().GET("/api/configuration");

        expect(response.status).toBe(401);
        expect(refreshCalls).toBe(1);
        expect(authStore.accessToken).toBe("expired-access-token");
    });
});
