import { GalaxyApi } from "@/api/client";
import { rethrowSimple } from "@/utils/simple-error";

export class Services {
    async decode(id) {
        try {
            return await GalaxyApi().GET("/api/configuration/decode/{id}", {
                params: { path: { id } },
            });
        } catch (e) {
            rethrowSimple(e);
        }
    }
}
