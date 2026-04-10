import { createTestingPinia } from "@pinia/testing";
import { getLocalVue, injectTestRouter } from "@tests/vitest/helpers";
import { mount } from "@vue/test-utils";
import flushPromises from "flush-promises";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HttpResponse, useServerMock } from "@/api/client/__mocks__";

import MountTarget from "./RegisterForm.vue";

const localVue = getLocalVue(true);
const router = injectTestRouter(localVue);
const { server, http } = useServerMock();

describe("RegisterForm", () => {
    beforeEach(() => {
        server.use(
            http.get("/api/configuration", ({ response }) => {
                return response.untyped(HttpResponse.json({ oidc: { cilogon: false } }));
            }),
            http.untyped.post(/.*\/auth\/register.*/, async () => {
                return HttpResponse.json({});
            }),
        );
    });

    it("basics", async () => {
        const pinia = createTestingPinia({ createSpy: vi.fn, stubActions: false });
        const wrapper = mount(MountTarget as object, {
            localVue,
            pinia,
            router,
        });

        const cardHeader = wrapper.find(".card-header");
        expect(cardHeader.text()).toContain("Create a Galaxy account");

        const inputs = wrapper.findAll("input");
        expect(inputs.length).toBe(4);

        const emailField = inputs.at(0);
        expect(emailField.attributes("type")).toBe("text");
        await emailField.setValue("test_user@test.org");

        const pwdField = inputs.at(1);
        expect(pwdField.attributes("type")).toBe("password");
        await pwdField.setValue("test_pwd");

        const confirmField = inputs.at(2);
        expect(confirmField.attributes("type")).toBe("password");
        await confirmField.setValue("test_pwd");

        const usernameField = inputs.at(3);
        expect(usernameField.attributes("type")).toBe("text");
        await usernameField.setValue("test_user");
    });

    it("redirects directly after registration", async () => {
        const pinia = createTestingPinia({ createSpy: vi.fn, stubActions: false });
        const assign = vi.spyOn(window.location, "assign").mockImplementation(() => undefined);

        const wrapper = mount(MountTarget as object, {
            localVue,
            pinia,
            propsData: {
                redirect: "/user",
            },
            router,
        });

        await wrapper.find("input#register-form-email").setValue("test_user@test.org");
        await wrapper.find("input#register-form-password").setValue("test_pwd");
        await wrapper.find("input#register-form-confirm").setValue("test_pwd");
        await wrapper.find("input#register-form-username").setValue("test_user");
        await wrapper.find("button[type='submit']").trigger("submit");
        await flushPromises();

        expect(assign).toHaveBeenCalledWith("/user");
        assign.mockRestore();
    });

    // TODO: Changing the original `<a>` to a `GLink` has made it so that the link never appears in the wrapper.
    // it("switching from Register to Login", async () => {
    //     const cardHeader = await wrapper.find(".card-header");
    //     // TODO: fix typing, see note in ExportForm.test.ts
    //     (expect(cardHeader.text()) as any).toBeLocalizationOf("Create a Galaxy account");

    //     const loginToggle = wrapper.find(SELECTORS.LOGIN_TOGGLE); // TODO: Never appears because of the GLink change
    //     expect(loginToggle.exists()).toBeTruthy();

    //     await wrapper.setProps({ hideLoginLink: true });
    //     const missingToggle = wrapper.find(SELECTORS.LOGIN_TOGGLE);
    //     expect(missingToggle.exists()).toBeFalsy();
    // });
});
