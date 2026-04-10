import { GalaxyApi } from "@/api/client";
import { rethrowSimple } from "@/utils/simple-error";

export class Services {
    constructor(options = {}) {
        this.root = options.root || getAppRoot();
    }

    async getLibraryPermissions(id) {
        try {
            const { data } = await GalaxyApi().GET("/api/libraries/{library_id}/permissions", {
                params: { path: { library_id: id }, query: { scope: "current" } },
            });
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async getLibrary(id) {
        try {
            const { data } = await GalaxyApi().GET("/api/libraries/{library_id}", {
                params: { path: { library_id: id } },
            });
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async getFolderPermissions(id) {
        try {
            const { data } = await GalaxyApi().GET("/api/folders/{folder_id}/permissions", {
                params: { path: { folder_id: id }, query: { scope: "current" } },
            });
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async getDatasetPermissions(id) {
        try {
            const { data } = await GalaxyApi().GET("/api/libraries/datasets/{dataset_id}/permissions", {
                params: { path: { dataset_id: id }, query: { scope: "current" } },
            });
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async getDataset(id) {
        try {
            const { data } = await GalaxyApi().GET("/api/libraries/datasets/{dataset_id}", {
                params: { path: { dataset_id: id } },
            });
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async getFolder(id) {
        try {
            const { data } = await GalaxyApi().GET("/api/folders/{folder_id}", {
                params: { path: { folder_id: id } },
            });
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async getSelectOptions(apiRootUrl, id, is_library_access, page, page_limit, searchQuery) {
        try {
            const { data } = await GalaxyApi().GET(`${apiRootUrl}/{id}/permissions`, {
                params: {
                    path: { id },
                    query: {
                        scope: "available",
                        is_library_access,
                        page_limit,
                        page,
                        ...(searchQuery ? { q: searchQuery } : {}),
                    },
                },
            });
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async setPermissions(apiRootUrl, id, new_roles_ids, onSuccess, onError) {
        const data = { action: "set_permissions" };
        new_roles_ids.forEach((permissionType) => {
            Object.keys(permissionType).map(function (type) {
                const ids = permissionType[type].map((a) => a.id);
                data[type] = ids;
            });
        });

        GalaxyApi()
            .POST(`${apiRootUrl}/{id}/permissions`, {
                params: { path: { id } },
                body: data,
            })
            .then(function (response) {
                onSuccess(response);
            })
            .catch((response) => {
                onError(response);
            });
    }

    async toggleDatasetPrivacy(id, isMakePrivate, onSuccess, onError) {
        await GalaxyApi()
            .POST("/api/libraries/datasets/{dataset_id}/permissions", {
                params: {
                    path: { dataset_id: id },
                    query: { action: isMakePrivate ? "make_private" : "remove_restrictions" },
                },
            })
            .then((fetched_permissions) => {
                onSuccess(fetched_permissions.data);
            })
            .catch((response) => {
                onError(response);
            });
    }
}
