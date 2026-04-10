import { getLocalVue } from "@tests/vitest/helpers";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import MastheadItem from "./MastheadItem.vue";

const localVue = getLocalVue();

describe("MastheadItem.vue", () => {
    it("renders the login marker on the clickable anchor", async () => {
        const wrapper = mount(MastheadItem, {
            localVue,
            propsData: {
                dataDescription: "login masthead button",
                id: "user",
                title: "Login",
                url: "/login/start",
            },
        });

        const anchor = wrapper.find("a");

        expect(anchor.attributes("data-description")).toBe("login masthead button");
        expect(anchor.attributes("href")).toBe("/login/start");
    });

    it("emits click when the anchor is activated", async () => {
        const wrapper = mount(MastheadItem, {
            localVue,
            propsData: {
                id: "user",
                title: "Login",
                url: "/login/start",
            },
        });

        await wrapper.find("a").trigger("click");

        expect(wrapper.emitted("click")).toBeTruthy();
    });
});
