import { getLocalVue } from "@tests/vitest/helpers";
import { shallowMount } from "@vue/test-utils";
import flushPromises from "flush-promises";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ExternalIdentities from "./ExternalIdentities.vue";
import svc from "./service";

vi.mock("./service", () => ({
    default: {
        getIdentityProviders: vi.fn(),
        disconnectIdentity: vi.fn(),
    },
}));

vi.mock("@/app", () => ({
    getGalaxyInstance: () => ({
        config: {
            enable_oidc: true,
        },
        user: {
            get: (key: string) => (key === "email" ? "current@example.org" : null),
        },
    }),
}));

vi.mock("@/composables/toast", () => ({
    Toast: {
        success: vi.fn(),
    },
}));

const localVue = getLocalVue(true);

describe("ExternalIdentities", () => {
    beforeEach(() => {
        window.history.replaceState({}, "", "/user/external_ids");
        vi.mocked(svc.getIdentityProviders).mockResolvedValue([
            {
                id: 1,
                provider: "keycloak",
                provider_label: "Keycloak",
                email: "existing@example.org",
            },
            {
                id: 2,
                provider: "cilogon",
                provider_label: "CILogon",
                email: "second@example.org",
            },
        ]);
    });

    it("excludes already linked providers from the connect list", async () => {
        const wrapper = shallowMount(ExternalIdentities, {
            localVue,
            stubs: {
                ExternalLogin: {
                    name: "ExternalLogin",
                    props: ["excludeIdps"],
                    template: "<div />",
                },
                "b-alert": true,
                "b-button": true,
                "b-modal": true,
            },
        });

        await flushPromises();

        const externalLogin = wrapper.findComponent({ name: "ExternalLogin" });
        expect(externalLogin.exists()).toBe(true);
        expect(externalLogin.props("excludeIdps")).toEqual(["keycloak", "cilogon"]);
    });

    it("shows backend messages on the external identities page", async () => {
        window.history.replaceState({}, "", "/user/external_ids?message=Denied&status=danger");

        const wrapper = shallowMount(ExternalIdentities, {
            localVue,
            stubs: {
                ExternalLogin: {
                    name: "ExternalLogin",
                    props: ["excludeIdps"],
                    template: "<div />",
                },
                "b-alert": true,
                "b-button": true,
                "b-modal": true,
            },
        });

        await flushPromises();

        expect(wrapper.vm.errorMessage).toBe("Denied");
        expect(wrapper.vm.errorVariant).toBe("danger");
    });
});
