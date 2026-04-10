<template>
    <div />
</template>

<script>
import { GalaxyApi } from "@/api/client";

export default {
    data() {
        return { schemaTagObj: {} };
    },
    async created() {
        let tools = [];
        await GalaxyApi()
            .GET("/api/tools", {
                params: { query: { in_panel: false, tool_help: true } },
            })
            .then(({ data }) => {
                tools = data.reduce((acc, item) => {
                    acc[item.id] = item;
                    return acc;
                }, {});
            })
            .catch((error) => {
                console.error("List of all tools not loaded", error);
            });
        if (Object.keys(tools).length > 0) {
            await GalaxyApi()
                .GET("/api/tool_panels/default")
                .then(({ data }) => {
                    this.schemaTagObj = this.createToolsJson(tools, data);
                    const el = document.createElement("script");
                    el.id = "schema-json";
                    el.type = "application/ld+json";
                    el.text = JSON.stringify(this.schemaTagObj);
                    document.head.appendChild(el);
                })
                .catch((error) => {
                    console.error("Tool sections by id not loaded", error);
                });
        }
    },
    methods: {
        createToolsJson(tools, panel) {
            const sections = Object.values(panel);
            function extractSections(acc, section) {
                function extractTools(_acc, toolId) {
                    const tool = tools[toolId];
                    return tool && tool.name
                        ? [
                              ..._acc,
                              {
                                  "@type": "SoftwareApplication",
                                  operatingSystem: "Any",
                                  applicationCategory: "Web application",
                                  name: tool.name,
                                  description: tool.help || tool.description,
                            softwareVersion: tool.version,
                            url: String(tool.link),
                        },
                          ]
                        : _acc;
                }
                if ("tools" in section) {
                    return acc.concat(section.tools.reduce(extractTools, []));
                } else {
                    return acc;
                }
            }
            return {
                "@context": "http://schema.org",
                "@graph": sections.reduce(extractSections, []),
            };
        },
    },
};
</script>
