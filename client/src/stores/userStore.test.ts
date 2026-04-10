import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";

import { useHistoryStore } from "@/stores/historyStore";
import {
    addFavoriteToolQuery,
    getCurrentUser,
    removeFavoriteToolQuery,
    setCurrentThemeQuery,
} from "@/stores/users/queries";
import { useUserStore } from "@/stores/userStore";

import { useAuthStore } from "./authStore";

vi.mock("@/composables/hashedUserId", () => ({
    useHashedUserId: () => ({
        hashedUserId: ref(null),
    }),
}));

vi.mock("@/composables/userLocalStorageFromHashedId", () => ({
    useUserLocalStorageFromHashId: <T>(key: string, initialValue: T) => {
        return ref(initialValue) as { value: T };
    },
}));

vi.mock("@/stores/users/queries", () => ({
    addFavoriteToolQuery: vi.fn(),
    getCurrentUser: vi.fn(),
    removeFavoriteToolQuery: vi.fn(),
    setCurrentThemeQuery: vi.fn(),
}));

describe("userStore", () => {
    beforeEach(() => {
        setActivePinia(createPinia());
        vi.mocked(getCurrentUser).mockReset();
        vi.mocked(addFavoriteToolQuery).mockReset();
        vi.mocked(removeFavoriteToolQuery).mockReset();
        vi.mocked(setCurrentThemeQuery).mockReset();
    });
    afterEach(() => {
        const userStore = useUserStore();
        userStore.$reset();
    });

    describe("addRecentTool", () => {
        it("adds tools to the front, deduplicates, and ignores empty ids", () => {
            const userStore = useUserStore();

            userStore.addRecentTool("");
            expect(userStore.recentTools).toEqual([]);

            userStore.addRecentTool("tool_a");
            userStore.addRecentTool("tool_b");
            userStore.addRecentTool("tool_c");
            expect(userStore.recentTools).toEqual(["tool_c", "tool_b", "tool_a"]);

            // re-adding an existing tool moves it to front without duplicating
            userStore.addRecentTool("tool_a");
            expect(userStore.recentTools).toEqual(["tool_a", "tool_c", "tool_b"]);
        });

        it("drops the oldest tool when the limit is reached", () => {
            const userStore = useUserStore();
            for (let i = 0; i < 10; i++) {
                userStore.addRecentTool(`tool_${i}`);
            }
            expect(userStore.recentTools).toHaveLength(10);
            expect(userStore.recentTools[0]).toBe("tool_9");
            expect(userStore.recentTools[9]).toBe("tool_0");

            userStore.addRecentTool("tool_new");
            expect(userStore.recentTools).toHaveLength(10);
            expect(userStore.recentTools[0]).toBe("tool_new");
            expect(userStore.recentTools).not.toContain("tool_0");
        });
    });

    describe("clearRecentTools", () => {
        it("clears all recent tools", () => {
            const userStore = useUserStore();
            userStore.addRecentTool("tool_a");
            userStore.addRecentTool("tool_b");
            expect(userStore.recentTools).toHaveLength(2);

            userStore.clearRecentTools();
            expect(userStore.recentTools).toEqual([]);
        });
    });

    it("hydrates the current registered user from the API response", async () => {
        const userStore = useUserStore();
        vi.mocked(getCurrentUser).mockResolvedValue({
            email: "user@example.org",
            id: "encoded-user",
            is_admin: false,
            preferences: {
                favorites: JSON.stringify({ tools: ["tool_a"] }),
                theme: "dark",
            },
            username: "user",
        } as never);

        await userStore.loadUser(false);

        expect(userStore.isAnonymous).toBe(false);
        expect(userStore.currentUser?.username).toBe("user");
        expect(userStore.currentTheme).toBe("dark");
        expect(userStore.currentFavorites.tools).toEqual(["tool_a"]);
    });

    it("refreshes user state after auth changes", async () => {
        const authStore = useAuthStore();
        const userStore = useUserStore();
        vi.mocked(getCurrentUser).mockResolvedValue({
            email: "user@example.org",
            id: "encoded-user",
            is_admin: false,
            preferences: {
                favorites: JSON.stringify({ tools: ["tool_b"] }),
                theme: "light",
            },
            username: "user",
        } as never);

        authStore.bootstrapStatus = "ready";
        authStore.accessToken = "access-token";
        authStore.effectiveUser = {
            email: "user@example.org",
            id: "encoded-user",
            username: "user",
        };
        authStore.authStateVersion += 1;

        await nextTick();
        await Promise.resolve();

        expect(userStore.currentUser?.username).toBe("user");
        expect(userStore.currentTheme).toBe("light");
        expect(userStore.currentFavorites.tools).toEqual(["tool_b"]);

        authStore.clearAuthState();
        await nextTick();

        expect(userStore.currentUser).toBeNull();
        expect(userStore.currentPreferences).toBeNull();
    });

    it("updates theme and favorites for registered users", async () => {
        const userStore = useUserStore();
        userStore.currentUser = {
            email: "user@example.org",
            id: "encoded-user",
            is_admin: false,
            preferences: {
                favorites: JSON.stringify({ tools: [] }),
                theme: "light",
            },
            username: "user",
        } as never;
        userStore.currentPreferences = {
            favorites: { tools: [] },
            theme: "light",
        };

        vi.mocked(setCurrentThemeQuery).mockResolvedValue("dark");
        vi.mocked(addFavoriteToolQuery).mockResolvedValue(["tool_a"]);
        vi.mocked(removeFavoriteToolQuery).mockResolvedValue([]);

        await userStore.setCurrentTheme("dark");
        await userStore.addFavoriteTool("tool_a");
        await userStore.removeFavoriteTool("tool_a");

        expect(setCurrentThemeQuery).toHaveBeenCalledWith("encoded-user", "dark");
        expect(addFavoriteToolQuery).toHaveBeenCalledWith("encoded-user", "tool_a");
        expect(removeFavoriteToolQuery).toHaveBeenCalledWith("encoded-user", "tool_a");
        expect(userStore.currentTheme).toBe("dark");
        expect(userStore.currentFavorites.tools).toEqual([]);
    });

    it("does not update user-specific settings for anonymous users", async () => {
        const userStore = useUserStore();

        await userStore.setCurrentTheme("dark");
        await userStore.addFavoriteTool("tool_a");
        await userStore.removeFavoriteTool("tool_a");

        expect(setCurrentThemeQuery).not.toHaveBeenCalled();
        expect(addFavoriteToolQuery).not.toHaveBeenCalled();
        expect(removeFavoriteToolQuery).not.toHaveBeenCalled();
    });

    it("loads histories when the default user refresh is requested", async () => {
        const historyStore = useHistoryStore();
        const loadHistories = vi.spyOn(historyStore, "loadHistories").mockResolvedValue(undefined);
        const userStore = useUserStore();
        vi.mocked(getCurrentUser).mockResolvedValue({
            email: "user@example.org",
            id: "encoded-user",
            is_admin: false,
            preferences: {
                favorites: JSON.stringify({ tools: [] }),
                theme: "dark",
            },
            username: "user",
        } as never);

        await userStore.loadUser();

        expect(loadHistories).toHaveBeenCalledTimes(1);
    });

    it("clears user state immediately when auth is removed", async () => {
        const authStore = useAuthStore();
        const userStore = useUserStore();
        vi.mocked(getCurrentUser).mockResolvedValue({
            email: "user@example.org",
            id: "encoded-user",
            is_admin: false,
            preferences: {
                favorites: JSON.stringify({ tools: ["tool_b"] }),
                theme: "light",
            },
            username: "user",
        } as never);

        authStore.bootstrapStatus = "ready";
        authStore.accessToken = "access-token";
        authStore.effectiveUser = {
            email: "user@example.org",
            id: "encoded-user",
            username: "user",
        };
        authStore.authStateVersion += 1;
        await nextTick();

        expect(userStore.currentUser?.username).toBe("user");

        vi.mocked(getCurrentUser).mockClear();
        authStore.clearAuthState();
        await nextTick();

        expect(userStore.currentUser).toBeNull();
        expect(userStore.currentPreferences).toBeNull();
        expect(userStore.recentTools).toEqual([]);
        expect(vi.mocked(getCurrentUser)).not.toHaveBeenCalled();
    });
});
