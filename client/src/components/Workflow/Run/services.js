/**
 * Service layer for interaction for the workflow run API.
 */
import { GalaxyApi } from "@/api";
import { rethrowSimple } from "@/utils/simple-error";

/**
 * Download the workflow using the 'run' style (see workflow manager on backend
 * for implementation). This contains the data needed to render the UI for workflows.
 *
 * @param {String} workflowId - (Stored?) Workflow ID to fetch data for.
 * @param {String} version - Version of the workflow to fetch.
 */
export async function getRunData(workflowId, version = null, instance = false) {
    try {
        const { data, error } = await GalaxyApi().GET("/api/workflows/{workflow_id}/download", {
            params: {
                path: { workflow_id: workflowId },
                query: { style: "run", instance, ...(version ? { version } : {}) },
            },
        });
        if (error) {
            throw error;
        }
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

/**
 * Invoke the specified workflow using the supplied data.
 *
 * @param {String} workflowId - (Stored?) Workflow ID to fetch data for.
 */
export async function invokeWorkflow(workflowId, invocationData) {
    const { data, error } = await GalaxyApi().POST("/api/workflows/{workflow_id}/invocations", {
        params: { path: { workflow_id: workflowId } },
        body: invocationData,
    });
    if (error) {
        throw error;
    }
    return data;
}

/**
 * Request tool step data.
 *
 * @param {String} toolId - Tool ID to fetch data for.
 * @param {String} toolVersion - Corresponding tool version.
 * @param {Object} toolInputs - Current tool state.
 * @param {Object} historyId - History ID to populate data selection fields.
 */
export async function getTool(toolId, toolVersion, toolInputs, historyId) {
    const requestData = {
        tool_id: toolId,
        tool_version: toolVersion,
        inputs: JSON.parse(JSON.stringify(toolInputs)),
        history_id: historyId,
    };
    try {
        const { data, error } = await GalaxyApi().POST("/api/tools/{tool_id}/build", {
            params: { path: { tool_id: toolId } },
            body: requestData,
        });
        if (error) {
            throw error;
        }
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}
