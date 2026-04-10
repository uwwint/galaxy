import { GalaxyApi } from "@/api";
import { getAppRoot } from "@/onload/appRoot";

let cachedConfig = null;

export async function loadConfig() {
    if (!cachedConfig) {
        try {
            const { data, error } = await GalaxyApi().GET("/context");
            if (error) {
                throw error;
            }
            cachedConfig = data;
        } catch (err) {
            console.error("Failed to load Galaxy configuration:", err);
            return {};
        }
    }
    return cachedConfig;
}

/**
 * Finds <link rel="index"> in head element and pulls root url fragment from
 * there.
 *
 * @param {string} [defaultRoot="/"]
 * @returns {string}
 */
export { getAppRoot };
