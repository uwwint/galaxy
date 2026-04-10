import { GalaxyApi } from "@/api/client";
import { rethrowSimple } from "@/utils/simple-error";

export async function save(pageId, content, showProgress = true) {
    try {
        const response = await GalaxyApi().POST("/api/pages/{page_id}/revisions", {
            params: { path: { page_id: pageId } },
            body: { content: content },
        });
        return response;
    } catch (e) {
        rethrowSimple(e);
    }
}
