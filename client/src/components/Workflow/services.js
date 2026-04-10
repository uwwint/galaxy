import { GalaxyApi } from "@/api/client";
import { useAuthStore } from "@/stores/authStore";
import { rethrowSimple } from "@/utils/simple-error";

import { toSimple } from "./Editor/modules/model";

/** Workflow data request helper **/
export class Services {
    async copyWorkflow(workflow) {
        const authStore = useAuthStore();
        const currentUsername = authStore.effectiveUser?.username;
        try {
            const { data: newWorkflow } = await GalaxyApi().GET("/api/workflows/{workflow_id}/download", {
                params: { path: { workflow_id: workflow.id } },
            });
            const currentOwner = workflow.owner;
            let newName = `Copy of ${workflow.name}`;
            if (currentOwner != currentUsername) {
                newName += ` shared by user ${currentOwner}`;
            }
            newWorkflow.name = newName;
            const { data: createWorkflow } = await GalaxyApi().POST("/api/workflows", {
                body: { workflow: newWorkflow },
            });
            this._addAttributes(createWorkflow);
            return createWorkflow;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async createWorkflow(workflow) {
        try {
            const { data } = await GalaxyApi().POST("/api/workflows", {
                body: { workflow: toSimple(workflow.id, workflow), from_tool_form: true },
            });
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async deleteWorkflow(id) {
        try {
            const { data } = await GalaxyApi().DELETE("/api/workflows/{workflow_id}", {
                params: { path: { workflow_id: id } },
            });
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async undeleteWorkflow(id) {
        try {
            const { data } = await GalaxyApi().POST("/api/workflows/{workflow_id}/undelete", {
                params: { path: { workflow_id: id } },
            });
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async updateWorkflow(id, data) {
        try {
            const { data: workflowData } = await GalaxyApi().PUT("/api/workflows/{workflow_id}", {
                params: { path: { workflow_id: id } },
                body: data,
            });
            return workflowData;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    _addAttributes(workflow) {
        const authStore = useAuthStore();
        workflow.shared = workflow.owner !== authStore.effectiveUser?.username;
        workflow.description = "";
        if (workflow.annotations && workflow.annotations.length > 0) {
            const description = workflow.annotations[0].trim();
            if (description) {
                workflow.description = description;
            }
        }
    }

    async getTrsServers() {
        try {
            const { data } = await GalaxyApi().GET("/api/trs_consume/servers");
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async getTrsTool(trsServer, toolId) {
        // Due to the slashes in the toolId, WSGI doesn't work with
        // encodeURIComponent. I verified the framework is converting
        // the information and we're losing it. As ugly as Base64 is, it is
        // better than the alternatives IMO. -John
        // https://github.com/pallets/flask/issues/900
        toolId = btoa(toolId);
        try {
            const { data } = await GalaxyApi().GET("/api/trs_consume/{trs_server}/tools/{tool_id}", {
                params: {
                    path: { trs_server: trsServer, tool_id: toolId },
                    query: { tool_id_b64_encoded: true },
                },
            });
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async importTrsTool(trsServer, toolId, versionId) {
        const data = {
            archive_source: "trs_tool",
            trs_server: trsServer,
            trs_tool_id: toolId,
            trs_version_id: versionId,
        };
        try {
            const { data: workflowData } = await GalaxyApi().POST("/api/workflows", { body: data });
            return workflowData;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async importTrsToolFromUrl(trsUrl) {
        const data = {
            archive_source: "trs_tool",
            trs_url: trsUrl,
        };
        try {
            const { data: workflowData } = await GalaxyApi().POST("/api/workflows", { body: data });
            return workflowData;
        } catch (e) {
            rethrowSimple(e);
        }
    }
}
