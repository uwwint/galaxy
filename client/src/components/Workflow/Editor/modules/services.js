import { GalaxyApi } from "@/api";
import { errorMessageAsString, rethrowSimple } from "@/utils/simple-error";

import { toSimple } from "./model";

/** Workflow data request helper **/
export async function getVersions(id) {
    try {
        const { data, error } = await GalaxyApi().GET("/api/workflows/{workflow_id}/versions", {
            params: { path: { workflow_id: id } },
        });
        if (error) {
            throw error;
        }
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

export async function getModule(request_data, stepId, setLoadingState) {
    setLoadingState(stepId, true);
    try {
        const { data, error } = await GalaxyApi().POST("/api/workflows/build_module", {
            body: request_data,
        });
        if (error) {
            throw error;
        }
        setLoadingState(stepId, false);
        return data;
    } catch (e) {
        setLoadingState(stepId, false, errorMessageAsString(e));
        rethrowSimple(e);
    }
}

export async function saveWorkflow(workflow) {
    if (workflow.hasChanges) {
        try {
            const requestData = { workflow: toSimple(workflow.id, workflow), from_tool_form: true };
            const { data, error } = await GalaxyApi().PUT("/api/workflows/{workflow_id}", {
                params: { path: { workflow_id: workflow.id } },
                body: requestData,
            });
            if (error) {
                throw error;
            }
            workflow.name = data.name;
            workflow.hasChanges = false;
            workflow.stored = true;
            workflow.version = data.version;
            if (workflow.annotation || data.annotation) {
                workflow.annotation = data.annotation;
            }
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }
    return {};
}

export async function getToolPredictions(requestData) {
    try {
        const { data, error } = await GalaxyApi().POST("/api/workflows/get_tool_predictions", {
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
