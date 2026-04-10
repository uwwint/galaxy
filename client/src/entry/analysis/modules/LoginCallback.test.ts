import { mount } from "@vue/test-utils";
import flushPromises from "flush-promises";
import { beforeEach, describe, expect, it, vi } from "vitest";

import MountTarget from "./LoginCallback.vue";

const ensureBootstrap = vi.fn();
const replace = vi.fn().mockResolvedValue(undefined);

vi.mock("@/stores/authStore", () => ({
    useAuthStore: () => ({
        ensureBootstrap,
    }),
}));

vi.mock("@/utils/redirect", () => ({
    withPrefix: (value: string) => value,
}));

vi.mock("vue-router/composables", () => ({
    useRouter: () => ({
        currentRoute: {
            query: {
                redirect: "/user",
            },
        },
        replace,
    }),
}));

vi.mock("@/utils/simple-error", () => ({
    errorMessageAsString: () => "Login completion failed.",
}));

describe("LoginCallback", () => {
    beforeEach(() => {
        ensureBootstrap.mockReset();
        replace.mockReset();
        replace.mockResolvedValue(undefined);
    });

    it("bootstraps auth and redirects once the auth state is ready", async () => {
        ensureBootstrap.mockResolvedValue({
            access_token: "token",
            actor_user: null,
            auth_source: "galaxy_token",
            authenticated: true,
            current_history_id: "encoded-history",
            user: {
                email: "user@example.org",
                id: "encoded-user",
                username: "user",
            },
        });
        mount(MountTarget as object);
        await flushPromises();

        expect(ensureBootstrap).toHaveBeenCalledTimes(1);
        expect(replace).toHaveBeenCalledWith("/user");
    });

    it("shows an error message when auth bootstrap fails", async () => {
        ensureBootstrap.mockRejectedValue(new Error("boom"));
        const wrapper = mount(MountTarget as object);
        await flushPromises();

        expect(ensureBootstrap).toHaveBeenCalledTimes(1);
        expect(replace).not.toHaveBeenCalled();
        expect(wrapper.text()).toContain("Login completion failed.");
    });
});
