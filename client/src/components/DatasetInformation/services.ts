import { GalaxyApi } from "@/api/client";
import { rethrowSimple } from "@/utils/simple-error";

export async function setAttributes(datasetId: string, settings: object, operation: string) {
    const payload = {
        dataset_id: datasetId,
        operation: operation,
        ...settings,
    };

    try {
        const { data } = await GalaxyApi().PUT("/dataset/set_edit", {
            body: payload,
        });
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}
