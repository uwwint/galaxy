import { GalaxyApi } from "@/api/client";
import { SingleQueryProvider } from "@/components/providers/SingleQueryProvider";
import { rethrowSimple } from "@/utils/simple-error";

import { cleanPaginationParameters } from "./utils";

export function storedWorkflowsProvider(ctx, callback, extraParams = {}) {
    const { root, ...requestParams } = ctx;
    const cleanParams = cleanPaginationParameters(requestParams);
    const promise = GalaxyApi().GET("/api/workflows", {
        params: { query: { ...cleanParams, ...extraParams } },
    });

    // Must return a promise that resolves to an array of items
    return promise.then(({ data, response }) => {
        // Pluck the array of items off our axios response
        callback && callback({ data, response });
        // Must return an array of items or an empty array if an error occurred
        return data || [];
    });
}

async function storedWorkflowDetails({ storedWorkflowId }) {
    try {
        const { data } = await GalaxyApi().GET("/api/workflows/{workflow_id}", {
            params: { path: { workflow_id: storedWorkflowId } },
        });
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

export const StoredWorkflowDetailsProvider = SingleQueryProvider(storedWorkflowDetails);
