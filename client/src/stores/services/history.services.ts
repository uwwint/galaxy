import type { AnyHistory, HistorySummaryExtended } from "@/api";
import { GalaxyApi } from "@/api";
import { ApiError, errorMessageAsString, type GalaxyApiResult, rethrowSimple } from "@/utils/simple-error";

/**
 * Some current endpoints don't accept JSON, so we need to
 * do some massaging to send in old form post data.
 */
function formData(fields = {} as Record<string, any>) {
    return Object.keys(fields).reduce((result, fieldName) => {
        result.set(fieldName, fields[fieldName]);
        return result;
    }, new FormData());
}

/**
 * Extended history request parameters.
 * Retrieves additional details which are usually more "expensive".
 */
const extendedHistoryParams = {
    view: "summary",
    keys: "size,contents_active,user_id",
};

/**
 * Create a new history, select it as the current history, and return it if successful.
 * @return the new history or throws an error if new history creation fails
 */
export async function createAndSelectNewHistory() {
    const { data, error } = await GalaxyApi().POST("/api/histories", {
        body: { all_datasets: true, archive_type: "url" },
    });

    if (error) {
        rethrowSimple(error);
    }

    const newHistory = data as AnyHistory;
    const selectedHistory = await setCurrentHistoryOnServer(newHistory.id);
    return selectedHistory ?? newHistory;
}

/**
 * Get current history from server and return it.
 * @param since timestamp to get histories since
 * @return the current history
 */
export async function getCurrentHistoryFromServer(since: string | undefined = undefined) {
    const { data, error } = await GalaxyApi().GET("/api/histories/current", {
        params: since ? { query: { since } } : undefined,
    });

    if (error) {
        rethrowSimple(error);
    }

    return data;
}

/**
 * Set current history on server and return it.
 * @param historyId Encoded history id
 * @return the current history
 */
export async function setCurrentHistoryOnServer(historyId: string) {
    const { data, error } = await GalaxyApi().PUT("/api/histories/current/{history_id}", {
        params: { path: { history_id: historyId } },
    });

    if (error) {
        rethrowSimple(error);
    }

    return data;
}

/**
 * Get list of histories from server and return them.
 * @param offset to start from (default = 0)
 * @param limit of histories to load (default = null; in which case no limit)
 * @param queryString to append to url in the form `q=filter&qv=val&q=...`
 * @return list of histories
 */
export async function getHistoryList(offset = 0, limit: number | null = null, queryString = "") {
    const query = new URLSearchParams(queryString);
    const queryParams: Record<string, string | number> = {
        view: "summary",
        order: "update_time",
        offset,
    };
    if (limit !== null) {
        queryParams.limit = limit;
    }
    query.forEach((value, key) => {
        queryParams[key] = value;
    });
    const { data, error } = await GalaxyApi().GET("/api/histories", {
        params: { query: queryParams },
    });
    if (error) {
        rethrowSimple(error);
    }
    return data;
}

/** Load one history by id */
export async function getHistoryByIdFromServer(id: string): Promise<GalaxyApiResult<HistorySummaryExtended>> {
    const { data, error, response } = await GalaxyApi().GET("/api/histories/{history_id}", {
        params: {
            path: { history_id: id },
            query: extendedHistoryParams,
        },
    });

    if (error) {
        return { data: undefined, error: new ApiError(errorMessageAsString(error), response.status) };
    }

    // We know that the data is a HistorySummaryExtended because we requested it
    // with the extendedHistoryParams
    return { data: data as HistorySummaryExtended, error: undefined };
}

/**
 * Set permissions to private for indicated history
 * TODO: rewrite API endpoint for this
 * @param history the history to secure
 * @return the secured history
 */
export async function secureHistoryOnServer(history: AnyHistory) {
    const { id } = history;
    const { data, error, response } = await GalaxyApi().POST("/history/make_private" as never, {
        body: formData({ history_id: id }),
    });
    if (error || response.status !== 200) {
        throw new Error(response.statusText);
    }
    const result = await getHistoryByIdFromServer(id);
    if (result.error) {
        throw result.error;
    }
    return {
        securedHistory: result.data,
        message: data.message as string,
        sharingStatusChanged: data.sharing_status_changed as boolean,
    };
}

/**
 * Update specific fields in history
 * @param historyId the history id to update
 * @param payload fields to update
 * @return the updated history
 */
export async function updateHistoryFields(historyId: string, payload: Record<string, any>) {
    const { data, error } = await GalaxyApi().PUT("/api/histories/{history_id}", {
        params: {
            path: { history_id: historyId },
            query: extendedHistoryParams,
        },
        body: payload,
    });

    if (error) {
        rethrowSimple(error);
    }

    // We know that the data is a HistorySummaryExtended because we requested it
    // with the extendedHistoryParams
    return data as HistorySummaryExtended;
}
