import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { type Tool,useToolStore } from "./toolStore";

vi.mock("@/onload/loadConfig", () => ({
    getAppRoot: () => "/app/",
}));

function makeTool(modelClass: string): Tool {
    return {
        model_class: modelClass,
        id: "tool_id",
        name: "Tool name",
        version: "1.0.0",
        description: "",
        labels: [],
        edam_operations: [],
        edam_topics: [],
        hidden: false,
        is_workflow_compatible: false,
        xrefs: [],
        config_file: "tool.xml",
        link: "/tool.xml",
        min_width: 0,
        target: "galaxy_main",
        panel_section_id: "section_id",
        panel_section_name: "Section name",
        form_style: "regular",
    };
}

describe("toolStore", () => {
    beforeEach(() => {
        setActivePinia(createPinia());
    });

    it("routes data source tools through the auth tool runner handoff", () => {
        const toolStore = useToolStore();
        toolStore.toolsById = {
            data_source: makeTool("DataSourceTool"),
        };

        expect(toolStore.getLinkById("data_source")).toBe("/app/auth/tool_runner?tool_id=data_source");
        expect(toolStore.getTargetById("data_source")).toBe("_top");
    });

    it("keeps non-data source tools on the normal launcher path", () => {
        const toolStore = useToolStore();
        toolStore.toolsById = {
            regular_tool: makeTool("Tool"),
        };

        expect(toolStore.getLinkById("regular_tool")).toBe("/app/?tool_id=regular_tool&version=latest");
        expect(toolStore.getTargetById("regular_tool")).toBe("galaxy_main");
    });
});
