import { GalaxyApi } from "@/api/client";
import { rethrowSimple } from "@/utils/simple-error";

export async function copyCollection(hdcaId, historyId) {
    const payload = {
        source: "hdca",
        type: "dataset_collection",
        content: hdcaId,
        copy_elements: true,
    };
    try {
        const { data } = await GalaxyApi().POST("/api/histories/{history_id}/contents/dataset_collections", {
            params: { path: { history_id: historyId } },
            body: payload,
        });
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}
