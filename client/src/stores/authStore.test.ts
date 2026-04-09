import axios from "axios";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

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

describe("authStore", () => {
    beforeEach(() => {
        setActivePinia(createPinia());
        vi.mocked(axios.post).mockReset();
    });

    it("bootstraps access token state from the backend response", async () => {
        const accessToken = makeAccessToken();
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

        expect(axios.post).toHaveBeenCalledWith("/auth/bootstrap", null, undefined);
        expect(authStore.accessToken).toBe(accessToken);
        expect(authStore.isAuthenticated).toBe(true);
        expect(authStore.currentHistoryId).toBe("encoded-history");
    });

    it("clears auth state on logout", async () => {
        vi.mocked(axios.post).mockResolvedValue({
            data: {
                message: "Success.",
            },
        });

        const authStore = useAuthStore();
        authStore.accessToken = makeAccessToken();
        authStore.authSource = "galaxy_token";

        await authStore.logout();

        expect(axios.post).toHaveBeenCalledWith("/auth/logout", null, {
            params: {
                logout_all: false,
            },
        });
        expect(authStore.accessToken).toBeNull();
        expect(authStore.isAuthenticated).toBe(false);
        expect(authStore.authSource).toBeNull();
    });
});
