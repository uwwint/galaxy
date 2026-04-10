import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";

import { useHistoryStore } from "@/stores/historyStore";
import { getCurrentHistoryFromServer } from "@/stores/services/history.services";

import { useAuthStore } from "./authStore";

vi.mock("@/composables/resourceWatcher", () => ({
    useResourceWatcher: () => ({
        startWatchingResource: vi.fn(),
        isWatchingResource: ref(false),
    }),
}));

vi.mock("@/composables/userLocalStorage", () => ({
    useUserLocalStorage: <T>(key: string, initialValue: T) => {
        return ref(initialValue) as { value: T };
    },
}));

vi.mock("@/stores/services/history.services", () => ({
    createAndSelectNewHistory: vi.fn(),
    getCurrentHistoryFromServer: vi.fn(),
    getHistoryByIdFromServer: vi.fn(),
    getHistoryList: vi.fn(),
    secureHistoryOnServer: vi.fn(),
    setCurrentHistoryOnServer: vi.fn(),
    updateHistoryFields: vi.fn(),
}));

describe("historyStore auth sync", () => {
    beforeEach(() => {
        setActivePinia(createPinia());
        vi.mocked(getCurrentHistoryFromServer).mockReset();
    });

    it("loads and restores the current history after auth changes", async () => {
        const authStore = useAuthStore();
        const historyStore = useHistoryStore();
        vi.mocked(getCurrentHistoryFromServer).mockResolvedValue({
            archived: false,
            id: "encoded-history",
            name: "Current history",
        } as never);

        authStore.bootstrapStatus = "ready";
        authStore.accessToken = "access-token";
        authStore.effectiveUser = {
            email: "user@example.org",
            id: "encoded-user",
            username: "user",
        };
        authStore.currentHistoryId = "encoded-history";
        authStore.authStateVersion += 1;

        await nextTick();
        await Promise.resolve();

        expect(getCurrentHistoryFromServer).toHaveBeenCalledTimes(1);
        expect(historyStore.currentHistoryId).toBe("encoded-history");
        expect(historyStore.currentHistory?.id).toBe("encoded-history");

        authStore.clearAuthState();
        await nextTick();

        expect(historyStore.currentHistoryId).toBeNull();
        expect(historyStore.currentHistory).toBeNull();
    });
});
