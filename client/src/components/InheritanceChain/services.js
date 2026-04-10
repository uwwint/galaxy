import { GalaxyApi } from "@/api/client";
import { rethrowSimple } from "@/utils/simple-error";

export class Services {
    async getInheritanceChain(datasetId) {
        try {
            const { data } = await GalaxyApi().GET("/api/datasets/{dataset_id}/inheritance_chain", {
                params: { path: { dataset_id: datasetId } },
            });
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    catch(e) {
        rethrowSimple(e);
    }
}
