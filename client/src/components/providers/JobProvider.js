import { GalaxyApi } from "@/api/client";
import { SingleQueryProvider } from "@/components/providers/SingleQueryProvider";
import { rethrowSimple } from "@/utils/simple-error";

import { cleanPaginationParameters, stateIsTerminal } from "./utils";

async function jobDetails({ jobId }) {
    try {
        const { data } = await GalaxyApi().GET("/api/jobs/{job_id}", {
            params: { path: { job_id: jobId }, query: { full: true } },
        });
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

async function jobConsoleOutput({
    jobId,
    stdout_position = 0,
    stdout_length = 0,
    stderr_position = 0,
    stderr_length = 0,
}) {
    try {
        const { data, response, error } = await GalaxyApi().GET("/api/jobs/{job_id}/console_output", {
            params: {
                path: { job_id: jobId },
                query: { stdout_position, stdout_length, stderr_position, stderr_length },
            },
        });
        if (error) {
            if (response.status === 403 && error.err_code == 403004) {
                console.log("This job destination does not support console output");
                return { state: "ok" };
            }
            throw Error("Problem fetching state");
        }
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

export const JobDetailsProvider = SingleQueryProvider(jobDetails, stateIsTerminal);
export const JobConsoleOutputProvider = SingleQueryProvider(jobConsoleOutput, stateIsTerminal);

export function jobsProvider(ctx, callback, extraParams = {}) {
    const { root, ...requestParams } = ctx;
    const cleanParams = cleanPaginationParameters(requestParams);
    const promise = GalaxyApi().GET("/api/jobs", {
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
