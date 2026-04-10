import { beforeEach, describe, expect, it, vi } from "vitest";

vi.setConfig({ testTimeout: 20_000 });

const ensureBootstrap = vi.fn();
const authStore = {
    accessToken: null as string | null,
    bootstrapStatus: "ready" as "idle" | "loading" | "ready" | "error",
    ensureBootstrap,
    effectiveUser: null as { id: string } | null,
    isAuthenticated: false,
};

vi.mock("@/stores/authStore", () => ({
    useAuthStore: () => authStore,
}));

vi.mock("vue-router", () => {
    function VueRouterMock(this: { beforeHooks?: unknown[]; errorHooks?: unknown[]; options?: unknown; routes?: unknown[] }, options: {
        routes: unknown[];
    }) {
        this.options = options;
        this.routes = options.routes;
        this.beforeHooks = [];
        this.errorHooks = [];
    }

    VueRouterMock.install = () => undefined;
    VueRouterMock.prototype.beforeEach = function beforeEach(hook: unknown) {
        this.beforeHooks.push(hook);
    };
    VueRouterMock.prototype.onError = function onError(hook: unknown) {
        this.errorHooks.push(hook);
    };

    return {
        default: VueRouterMock,
    };
});

vi.mock("@/entry/analysis/modules/Analysis.vue", () => ({
    default: { name: "Analysis", template: "<div />" },
}));

vi.mock("@/entry/analysis/modules/Home.vue", () => ({
    default: { name: "Home", template: "<div />" },
}));

vi.mock("@/entry/analysis/modules/Login.vue", () => ({
    default: { name: "Login", template: "<div />" },
}));

vi.mock("@/entry/analysis/modules/Register.vue", () => ({
    default: { name: "Register", template: "<div />" },
}));

vi.mock("@/entry/analysis/modules/LoginCallback.vue", () => ({
    default: { name: "LoginCallback", template: "<div />" },
}));

vi.mock("@/components/User/UserPreferences.vue", () => ({
    default: { name: "UserPreferences", template: "<div />" },
}));

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

function createDeferred<T>() {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((promiseResolve) => {
        resolve = promiseResolve;
    });
    return { promise, resolve };
}

function buildGalaxy() {
    return {
        config: {},
        user: {
            id: "encoded-user",
            isAdmin: () => false,
            isAnonymous: () => true,
        },
    } as never;
}

async function loadRouter() {
    const { getRouter } = await import("./router");
    return getRouter;
}

function findRoute(routes: Array<{ children?: Array<{ children?: unknown[]; path: string }>; path: string }>, path: string) {
    for (const route of routes) {
        if (route.path === path) {
            return route;
        }
        const child = route.children ? findRoute(route.children as never, path) : null;
        if (child) {
            return child;
        }
    }
    return null;
}

describe("analysis router", () => {
    beforeEach(() => {
        ensureBootstrap.mockReset();
        authStore.accessToken = null;
        authStore.bootstrapStatus = "ready";
        authStore.effectiveUser = null;
        authStore.isAuthenticated = false;
        installLocalStorage();
    });

    it("registers the expected auth routes and route guards", async () => {
        const getRouter = await loadRouter();
        const router = getRouter(buildGalaxy());

        const loginRoute = findRoute(router.routes, "/login/start");
        const registerRoute = findRoute(router.routes, "/register/start");
        const userRoute = findRoute(router.routes, "user");

        expect(loginRoute).toBeTruthy();
        expect(registerRoute).toBeTruthy();
        expect(userRoute).toBeTruthy();
        expect((userRoute as { beforeEnter?: unknown }).beforeEnter).toBeTypeOf("function");
        expect((loginRoute as { redirect?: () => string | undefined }).redirect?.()).toBeUndefined();
        expect((registerRoute as { redirect?: () => string | undefined }).redirect?.()).toBeUndefined();

        authStore.isAuthenticated = true;
        expect((loginRoute as { redirect?: () => string | undefined }).redirect?.()).toBe("/");
        expect((registerRoute as { redirect?: () => string | undefined }).redirect?.()).toBe("/");
    });

    it("waits for auth bootstrap before continuing navigation", async () => {
        const deferred = createDeferred<void>();
        ensureBootstrap.mockReturnValue(deferred.promise);

        const getRouter = await loadRouter();
        const router = getRouter(buildGalaxy());
        const beforeEachHook = router.beforeHooks[0] as (
            to: { path: string; fullPath: string },
            from: unknown,
            next: (location?: string | { path: string; query?: Record<string, string> }) => void,
        ) => Promise<void>;
        const next = vi.fn();
        const navigation = beforeEachHook({ path: "/", fullPath: "/", matched: [] }, null, next);

        await Promise.resolve();
        expect(next).not.toHaveBeenCalled();

        deferred.resolve();
        await deferred.promise;
        await navigation;

        expect(next).toHaveBeenCalledWith();
    });
});
