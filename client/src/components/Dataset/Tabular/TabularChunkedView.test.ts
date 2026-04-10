import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import flushPromises from "flush-promises";
import { describe, expect, it, vi } from "vitest";

import { useServerMock } from "@/api/client/__mocks__";

import TabularChunkedView from "./TabularChunkedView.vue";

const { server, http } = useServerMock();

describe("TabularChunkedView", () => {
    it("loads tabular chunks through the dataset display API", async () => {
        const datasetId = "dataset_1";
        server.use(
            http.get("/api/datasets/{history_content_id}/display", ({ request, response }) => {
                const url = new URL(request.url);
                expect(url.searchParams.get("offset")).toBe("0");
                return response(200).json({
                    ck_data: "1\t2\n3\t4\n",
                    offset: 10,
                    data_line_offset: 0,
                });
            }),
        );

        const wrapper = mount(TabularChunkedView, {
            pinia: createTestingPinia({ createSpy: vi.fn, stubActions: false }),
            propsData: {
                options: {
                    id: datasetId,
                    file_ext: "tabular",
                    metadata_columns: 2,
                    metadata_column_names: ["A", "B"],
                },
            },
        });

        await flushPromises();

        expect(wrapper.find("table").exists()).toBe(true);
        expect(wrapper.findAll("td")).toHaveLength(4);
        expect(wrapper.findAll("th")).toHaveLength(2);
    });
});
