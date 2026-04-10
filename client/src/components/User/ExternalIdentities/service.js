import { GalaxyApi } from "@/api";

export async function disconnectIdentity(doomed) {
    if (doomed) {
        let path;
        if (doomed.provider === "cilogon") {
            path = `/authnz/${doomed.provider}/disconnect/${doomed.email}`;
        } else {
            path = `/authnz/${doomed.provider}/disconnect/`;
        }

        const { response, error } = await GalaxyApi().DELETE(path);
        if (error || response.status != 200) {
            throw new Error("Delete failure.");
        }
    }
}

// Memoize results (basically never changes)
let identityProviders;

export async function getIdentityProviders() {
    const { data, error, response } = await GalaxyApi().GET("/authnz");
    if (error || response.status != 200) {
        throw new Error("Unable to load connected external identities");
    }
    identityProviders = data;
    return identityProviders;
}

export async function saveIdentity(idp) {
    const { response, error } = await GalaxyApi().POST(`/authnz/${idp}/login`);
    if (error || response.status != 200) {
        throw new Error("Save failure.");
    }
    return response;
}

export async function hasUsername() {
    const result = getCurrentUser();
    console.log(result.username);
    return getCurrentUser().username;
}

export async function getCurrentUser() {
    const { data, error } = await GalaxyApi().GET("/api/users/current");
    if (error) {
        throw error;
    }
    return data;
}

export default {
    saveIdentity,
    disconnectIdentity,
    getIdentityProviders,
    hasUsername,
};
