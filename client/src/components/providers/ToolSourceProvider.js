import beautify from "xml-beautifier";
import { stringify } from "yaml";

import { GalaxyApi } from "@/api/client";
import { SingleQueryProvider } from "@/components/providers/SingleQueryProvider";
import { rethrowSimple } from "@/utils/simple-error";

async function toolSource({ id, uuid }) {
    try {
        const { data, response } = await GalaxyApi().GET("/api/tools/{tool_id}/raw_tool_source", {
            params: { path: { tool_id: id || uuid }, ...(uuid ? { query: { tool_uuid: uuid } } : {}) },
        });
        const headers = response.headers;
        const result = {};
        result.language = headers.language;
        if (headers.language === "xml") {
            result.source = beautify(data);
        } else if (headers.language == "yaml") {
            result.source = stringify(data);
        } else {
            result.source = data;
        }
        return result;
    } catch (e) {
        rethrowSimple(e);
    }
}

export const ToolSourceProvider = SingleQueryProvider(toolSource);
