import { GalaxyApi } from "@/api/client";
import { cleanPaginationParameters } from "./utils";

export function invocationsProvider(ctx, callback, extraParams) {
    const { root, ...requestParams } = ctx;
    const cleanParams = cleanPaginationParameters(requestParams);
    const promise = GalaxyApi().GET("/api/invocations", {
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
