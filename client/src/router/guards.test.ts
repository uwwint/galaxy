import { beforeEach, describe, expect, it, vi } from "vitest";

import { requireAuth } from "./guards";

const ensureBootstrap = vi.fn();
const authStore = {
    accessToken: null as string | null,
    bootstrapStatus: "ready" as "idle" | "loading" | "ready" | "error",
    ensureBootstrap,
    effectiveUser: null as { id: string } | null,
};

function createDeferred<T>() {
    let resolve!: (value: T) => void;
    let reject!: (reason?: unknown) => void;
    const promise = new Promise<T>((promiseResolve, promiseReject) => {
        resolve = promiseResolve;
        reject = promiseReject;
    });
    return { promise, resolve, reject };
}

vi.mock("@/stores/authStore", () => ({
    useAuthStore: () => authStore,
}));

describe("requireAuth", () => {
    beforeEach(() => {
        ensureBootstrap.mockReset();
        authStore.accessToken = null;
        authStore.bootstrapStatus = "ready";
        authStore.effectiveUser = null;
    });

    it("redirects anonymous users after bootstrap", async () => {
        ensureBootstrap.mockResolvedValue({
            access_token: null,
            actor_user: null,
            auth_source: "anonymous",
            authenticated: false,
            current_history_id: null,
            user: null,
        });
        authStore.accessToken = null;
        authStore.effectiveUser = null;

        const next = vi.fn();
        await requireAuth({ fullPath: "/user" } as never, {} as never, next);

        expect(ensureBootstrap).toHaveBeenCalledTimes(1);
        expect(next).toHaveBeenCalledWith({
            path: "/login/start",
            query: {
                redirect: "/user",
            },
        });
    });

    it("allows registered users after bootstrap", async () => {
        ensureBootstrap.mockResolvedValue({
            access_token: "token",
            actor_user: null,
            auth_source: "galaxy_token",
            authenticated: true,
            current_history_id: "encoded-history",
            user: {
                id: "encoded-user",
            },
        });
        authStore.accessToken = "token";
        authStore.effectiveUser = { id: "encoded-user" };

        const next = vi.fn();
        await requireAuth({ fullPath: "/user" } as never, {} as never, next);

        expect(ensureBootstrap).toHaveBeenCalledTimes(1);
        expect(next).toHaveBeenCalledWith();
    });

    it("waits for bootstrap to settle before redirecting anonymous users", async () => {
        const deferred = createDeferred<never>();
        ensureBootstrap.mockReturnValue(deferred.promise);
        authStore.accessToken = null;
        authStore.effectiveUser = null;

        const next = vi.fn();
        const guard = requireAuth({ fullPath: "/user" } as never, {} as never, next);

        await Promise.resolve();
        expect(next).not.toHaveBeenCalled();

        deferred.resolve(undefined as never);
        await guard;

        expect(ensureBootstrap).toHaveBeenCalledTimes(1);
        expect(next).toHaveBeenCalledWith({
            path: "/login/start",
            query: {
                redirect: "/user",
            },
        });
    });
});
