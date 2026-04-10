import { mount } from "@vue/test-utils";
import flushPromises from "flush-promises";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { reactive, ref } from "vue";

import App from "./App.vue";

const ensureBootstrap = vi.fn();
const clearAuthState = vi.fn();
const resetUserStore = vi.fn();
const startWatchingEntryPoints = vi.fn();
const startWatchingNotifications = vi.fn();
const startWatchingHistory = vi.fn();
const setTour = vi.fn();

const authStore = reactive({
    ensureBootstrap,
    clearAuthState,
    bootstrapStatus: "idle",
    accessToken: null as string | null,
});

const userStore = reactive({
    $reset: resetUserStore,
    currentTheme: "default",
});

const historyStore = reactive({
    startWatchingHistory,
});

const entryPointStore = reactive({
    startWatchingEntryPoints,
});

const notificationsStore = reactive({
    startWatchingNotifications,
});

const tourStore = reactive({
    currentTour: ref(null),
    setTour,
});

const galaxy = reactive({
    config: {
        interactivetools_enable: false,
        enable_notification_system: false,
        themes: {},
        user_activation_on: false,
    },
    user: {
        id: "encoded-user",
        isAdmin: () => false,
        isAnonymous: () => true,
        get: vi.fn(() => false),
    },
    frame: null as null | { restore: () => void; getTab: () => null },
});

const route = reactive({
    fullPath: "/",
    params: {},
});

let embedded = false;

function installLocalStorage() {
    const storage = new Map<string, string>();
    Object.defineProperty(window, "localStorage", {
        configurable: true,
        value: {
            getItem: vi.fn((key: string) => storage.get(key) ?? null),
            setItem: vi.fn((key: string, value: string) => {
                storage.set(key, value);
            }),
            removeItem: vi.fn((key: string) => {
                storage.delete(key);
            }),
        },
    });
}

vi.mock("@/app", () => ({
    getGalaxyInstance: () => galaxy,
}));

vi.mock("@/onload", () => ({
    getAppRoot: () => "/",
}));

vi.mock("@/composables/route", () => ({
    useRouteQueryBool: () => ref(embedded),
}));

vi.mock("./window-manager", () => ({
    WindowManager: class {
        public active = false;
        public getTab() {
            return null;
        }
        public restore() {
            return undefined;
        }
        public beforeUnload() {
            return false;
        }
    },
}));

vi.mock("vue-router/composables", () => ({
    useRoute: () => route,
}));

vi.mock("@/stores/authStore", () => ({
    useAuthStore: () => authStore,
}));

vi.mock("@/stores/userStore", () => ({
    useUserStore: () => userStore,
}));

vi.mock("@/stores/historyStore", () => ({
    useHistoryStore: () => historyStore,
}));

vi.mock("@/stores/entryPointStore", () => ({
    useEntryPointStore: () => entryPointStore,
}));

vi.mock("@/stores/notificationsStore", () => ({
    useNotificationsStore: () => notificationsStore,
}));

vi.mock("@/stores/tourStore", () => ({
    useTourStore: () => tourStore,
}));

function mountApp() {
    return mount(App as object, {
        mocks: {
            $route: {
                query: {},
            },
            $router: {
                confirmation: null,
            },
        },
        stubs: {
            Alert: true,
            BroadcastsOverlay: true,
            ConfirmDialog: true,
            DragGhost: true,
            Masthead: true,
            Toast: true,
            TourRunner: true,
            UploadModal: true,
            "router-view": true,
        },
    });
}

describe("App", () => {
    beforeEach(() => {
        ensureBootstrap.mockReset();
        clearAuthState.mockReset();
        resetUserStore.mockReset();
        startWatchingEntryPoints.mockReset();
        startWatchingNotifications.mockReset();
        startWatchingHistory.mockReset();
        setTour.mockReset();
        route.fullPath = "/";
        route.params = {};
        embedded = false;
        galaxy.config.interactivetools_enable = false;
        galaxy.config.enable_notification_system = false;
        installLocalStorage();
    });

    it("boots auth without starting history polling at app startup", async () => {
        ensureBootstrap.mockResolvedValue(undefined);

        mountApp();
        await flushPromises();

        expect(ensureBootstrap).toHaveBeenCalledTimes(1);
        expect(startWatchingHistory).not.toHaveBeenCalled();
        expect(startWatchingEntryPoints).not.toHaveBeenCalled();
        expect(startWatchingNotifications).not.toHaveBeenCalled();
    });

    it("clears auth and user state when embedded", async () => {
        embedded = true;

        mountApp();
        await flushPromises();

        expect(clearAuthState).toHaveBeenCalledTimes(1);
        expect(resetUserStore).toHaveBeenCalledTimes(1);
        expect(ensureBootstrap).not.toHaveBeenCalled();
        expect(startWatchingHistory).not.toHaveBeenCalled();
    });
});
