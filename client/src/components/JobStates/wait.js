import { GalaxyApi } from "@/api/client";
import { ERROR_STATES, NON_TERMINAL_STATES } from "@/api/jobs";

export function waitOnJob(jobId, onStateUpdate = null, interval = 1000) {
    // full=true to capture standard error on last iteration for building
    // error messages.
    const checkCondition = function (resolve, reject) {
        GalaxyApi()
            .GET("/api/jobs/{job_id}", {
                params: { path: { job_id: jobId }, query: { full: true } },
            })
            .then((jobResponse) => {
                const state = jobResponse.data.state;
                if (onStateUpdate !== null) {
                    onStateUpdate(state);
                }
                if (NON_TERMINAL_STATES.indexOf(state) !== -1) {
                    setTimeout(checkCondition, interval, resolve, reject);
                } else if (ERROR_STATES.indexOf(state) !== -1) {
                    reject(jobResponse);
                } else {
                    resolve(jobResponse);
                }
            })
            .catch(reject);
    };

    return new Promise(checkCondition);
}
