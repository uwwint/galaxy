import { GalaxyApi } from "@/api/client";
import { rethrowSimple } from "@/utils/simple-error";

export class Services {
    async getFolderContents(folderId, includeDeleted, sortBy, sortDesc, limit, offset, searchText) {
        try {
            const { data } = await GalaxyApi().GET("/api/folders/{folder_id}/contents", {
                params: {
                    path: { folder_id: folderId },
                    query: {
                        include_deleted: includeDeleted,
                        sort_by: sortBy,
                        sort_desc: sortDesc,
                        limit,
                        offset,
                        ...(searchText.trim() ? { search_text: searchText.trim() } : {}),
                    },
                },
            });
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async getFilteredFolderContents(id, excluded, searchText, limit) {
        const { data } = await GalaxyApi().GET("/api/folders/{folder_id}/contents", {
            params: {
                path: { folder_id: id },
                query: { limit, ...(searchText?.trim() ? { search_text: searchText.trim() } : {}) },
            },
        });
        return data.folder_contents.filter((item) => !excluded.some((exc) => exc.id === item.id));
    }

    updateFolder(item, onSucess, onError) {
        GalaxyApi()
            .PATCH("/api/folders/{folder_id}", {
                params: { path: { folder_id: item.id } },
                body: item,
            })
            .then(() => {
                onSucess();
            })
            .catch((error) => {
                onError(error);
            });
    }

    newFolder(folder, onSucess, onError) {
        GalaxyApi()
            .POST("/api/folders/{folder_id}", {
                params: { path: { folder_id: folder.parent_id } },
                body: {
                    name: folder.name,
                    description: folder.description,
                },
            })
            .then((response) => {
                onSucess(response.data);
            })
            .catch((error) => {
                onError(error);
            });
    }

    undeleteFolder(folder, onSucess, onError) {
        GalaxyApi()
            .DELETE("/api/folders/{folder_id}", {
                params: { path: { folder_id: folder.id }, query: { undelete: true } },
            })
            .then((response) => {
                onSucess(response.data);
            })
            .catch((error) => {
                onError(error);
            });
    }

    undeleteDataset(dataset, onSucess, onError) {
        GalaxyApi()
            .DELETE("/api/libraries/datasets/{dataset_id}", {
                params: { path: { dataset_id: dataset.id }, query: { undelete: true } },
            })
            .then((response) => {
                onSucess(response.data);
            })
            .catch((error) => {
                onError(error);
            });
    }

    async getDataset(datasetID, onError) {
        try {
            const response = await GalaxyApi().GET("/api/libraries/datasets/{dataset_id}", {
                params: { path: { dataset_id: datasetID } },
            }).catch((error) => {
                onError(error);
            });
            return response.data;
        } catch (e) {
            rethrowSimple(e);
        }
    }

    async updateDataset(datasetID, data, onSucess, onError) {
        try {
            await GalaxyApi()
                .PATCH("/api/libraries/datasets/{dataset_id}", {
                    params: { path: { dataset_id: datasetID } },
                    body: data,
                })
                .then((response) => onSucess(response.data))
                .catch((error) => {
                    onError(error.err_msg);
                });
        } catch (e) {
            rethrowSimple(e);
        }
    }
}
