import { GalaxyApi } from "@/api/client";
import { rethrowSimple } from "@/utils/simple-error";

export class Services {
    async getLibraries(includeDeleted = false) {
        try {
            const { data } = await GalaxyApi().GET("/api/libraries", {
                params: { query: { deleted: includeDeleted } },
            });
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }
    async saveChanges(lib, onSucess, onError) {
        try {
            const { data } = await GalaxyApi().PATCH("/api/libraries/{library_id}", {
                params: { path: { library_id: lib.id } },
                body: lib,
            });
            onSucess(data);
            return data;
        } catch (e) {
            onError(e);
            rethrowSimple(e);
        }
    }
    async deleteLibrary(lib, onSucess, onError, isUndelete = false) {
        try {
            const { data } = await GalaxyApi().DELETE("/api/libraries/{library_id}", {
                params: { path: { library_id: lib.id }, query: isUndelete ? { undelete: true } : undefined },
            });
            onSucess(data);
            return data;
        } catch (e) {
            onError(e);
            rethrowSimple(e);
        }
    }
    async createNewLibrary(name, description, synopsis, onSucess, onError) {
        try {
            const { data } = await GalaxyApi().POST("/api/libraries", {
                body: {
                    name: name,
                    description: description,
                    synopsis: synopsis,
                },
            });
            onSucess(data);
            return data;
        } catch (e) {
            onError(e);
            rethrowSimple(e);
        }
    }
}
