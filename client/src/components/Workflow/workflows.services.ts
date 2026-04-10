import { GalaxyApi } from "@/api";
import type { WorkflowSummary } from "@/api/workflows";
import { useUserStore } from "@/stores/userStore";

export async function updateWorkflow(id: string, changes: object): Promise<WorkflowSummary> {
    const { data, error } = await GalaxyApi().PUT("/api/workflows/{workflow_id}" as never, {
        params: { path: { workflow_id: id } },
        body: changes,
    });
    if (error) {
        throw error;
    }
    return data;
}

export async function copyWorkflow(id: string, currentOwner?: string, version?: string): Promise<WorkflowSummary> {
    let path = `/api/workflows/${id}/download`;
    if (version) {
        path += `?version=${version}`;
    }
    const { data: workflowData, error } = await GalaxyApi().GET(path as never);
    if (error) {
        throw error;
    }

    workflowData.name = `Copy of ${workflowData.name}`;
    const userStore = useUserStore();

    if (!userStore.matchesCurrentUsername(currentOwner)) {
        workflowData.name += ` shared by user ${currentOwner}`;
    }

    const { data, error: createError } = await GalaxyApi().POST("/api/workflows", {
        body: { workflow: workflowData },
    });
    if (createError) {
        throw createError;
    }
    return data;
}

export async function deleteWorkflow(id: string): Promise<WorkflowSummary> {
    const { data, error } = await GalaxyApi().DELETE("/api/workflows/{workflow_id}" as never, {
        params: { path: { workflow_id: id } },
    });
    if (error) {
        throw error;
    }
    return data;
}

export async function createWorkflow(workflowName: string, workflowAnnotation: string) {
    const { data, error } = await GalaxyApi().PUT("/workflow/create" as never, {
        body: {
            workflow_name: workflowName,
            workflow_annotation: workflowAnnotation,
        },
    });
    if (error) {
        throw error;
    }
    return data;
}

export async function getWorkflowFull(workflowId: string, version?: number) {
    const params: { style: string; version?: number } = { style: "editor" };
    if (Number.isInteger(version)) {
        params.version = version;
    }
    const { data, error } = await GalaxyApi().GET("/api/workflows/{workflow_id}/download", {
        params: { path: { workflow_id: workflowId }, query: params },
    });
    if (error) {
        throw error;
    }
    return data;
}
