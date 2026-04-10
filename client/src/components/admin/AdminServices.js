import { GalaxyApi } from "@/api";
import { rethrowSimple } from "@/utils/simple-error";

export function getErrorStack() {
    return GalaxyApi().GET("/api/tools/error_stack");
}

export function getDisplayApplications() {
    return GalaxyApi().GET("/api/display_applications");
}

export function reloadDisplayApplications(ids) {
    return GalaxyApi().POST("/api/display_applications/reload", {
        body: { ids: ids },
    });
}

export function getInstalledRepositories() {
    return GalaxyApi().GET("/api/tool_shed_repositories", {
        params: { query: { uninstalled: false } },
    });
}

export function resetRepositoryMetadata(repository_ids) {
    return GalaxyApi().POST("/api/tool_shed_repositories/reset_metadata_on_selected_installed_repositories", {
        params: { query: { repository_ids } },
    });
}

export async function getDependencyUnusedPaths() {
    const params = {};
    try {
        const { data, error } = await GalaxyApi().GET("/api/dependency_resolvers/unused_paths", {
            params: { query: params },
        });
        if (error) {
            throw error;
        }
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

export async function deletedUnusedPaths(paths) {
    try {
        const { error } = await GalaxyApi().PUT("/api/dependency_resolvers/unused_paths", {
            body: { paths: paths },
        });
        if (error) {
            throw error;
        }
    } catch (e) {
        rethrowSimple(e);
    }
}

export async function getToolboxDependencies(params_) {
    const params = params_ || {};
    try {
        const { data, error } = await GalaxyApi().GET("/api/dependency_resolvers/toolbox", {
            params: { query: params },
        });
        if (error) {
            throw error;
        }
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

export async function installDependencies(toolIds, resolutionOptions) {
    const postData = { ...resolutionOptions, tool_ids: toolIds };
    try {
        const { data, error } = await GalaxyApi().POST("/api/dependency_resolvers/toolbox/install", {
            body: postData,
        });
        if (error) {
            throw error;
        }
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

export async function uninstallDependencies(toolIds, resolutionOptions) {
    const postData = { ...resolutionOptions, tool_ids: toolIds };
    try {
        const { data, error } = await GalaxyApi().POST("/api/dependency_resolvers/toolbox/uninstall", {
            body: postData,
        });
        if (error) {
            throw error;
        }
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

export async function getContainerResolutionToolbox(params_) {
    const params = params_ || {};
    try {
        const { data, error } = await GalaxyApi().GET("/api/container_resolvers/toolbox", {
            params: { query: params },
        });
        if (error) {
            throw error;
        }
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

export async function resolveContainersWithInstall(toolIds, params_) {
    const data = params_ || {};
    if (toolIds && toolIds.length > 0) {
        data.tool_ids = toolIds || [];
    }
    try {
        const result = await GalaxyApi().POST("/api/container_resolvers/toolbox/install", {
            body: data,
        });
        if (result.error) {
            throw result.error;
        }
        return result.data;
    } catch (e) {
        rethrowSimple(e);
    }
}
