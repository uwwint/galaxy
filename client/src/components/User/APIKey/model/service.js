import { GalaxyApi } from "@/api";

export async function getAPIKey(userId) {
    const { data, error, response } = await GalaxyApi().GET("/api/users/{user_id}/api_key/detailed", {
        params: { path: { user_id: userId } },
    });
    if (error) {
        throw error;
    }
    if (response.status === 204) {
        return [];
    }
    if (response.status !== 200) {
        throw new Error("Unexpected response retrieving the API key.");
    }
    return [data];
}

export async function createNewAPIKey(userId) {
    const { data, error, response } = await GalaxyApi().POST("/api/users/{user_id}/api_key", {
        params: { path: { user_id: userId } },
    });
    if (error || response.status !== 200) {
        throw new Error("Create API key failure.");
    }
    return data;
}

export async function deleteAPIKey(userId) {
    const { error, response } = await GalaxyApi().DELETE("/api/users/{user_id}/api_key", {
        params: { path: { user_id: userId } },
    });
    if (error || response.status !== 204) {
        throw new Error("Delete API Key failure.");
    }
}

export default {
    getAPIKey,
    createNewAPIKey,
    deleteAPIKey,
};
