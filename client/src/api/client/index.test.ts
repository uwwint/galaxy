import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import { HttpResponse, useServerMock } from "@/api/client/__mocks__";
import { useAuthStore } from "@/stores/authStore";

import { GalaxyApi } from "./index";

const { server, http } = useServerMock();

describe("GalaxyApi auth middleware", () => {
    beforeEach(() => {
        setActivePinia(createPinia());
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
});
