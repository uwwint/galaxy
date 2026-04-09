import createClient from "openapi-fetch";
import { getActivePinia } from "pinia";

import { createRateLimiterMiddleware } from "@/api/client/rateLimiter";
import type { GalaxyApiPaths } from "@/api/schema";
import { getAppRoot } from "@/onload/loadConfig";
import { useAuthStore } from "@/stores/authStore";

function getBaseUrl() {
    const isTest = process.env.NODE_ENV === "test";
    return isTest ? window.location.origin : getAppRoot().replace(/\/$/, "");
}

function apiClientFactory() {
    const client = createClient<GalaxyApiPaths>({ baseUrl: getBaseUrl() });

    client.use({
        onRequest({ request }) {
            const pinia = getActivePinia();
            if (!pinia) {
                return request;
            }
            const authStore = useAuthStore(pinia);
            if (!authStore.accessToken) {
                return request;
            }
            const headers = new Headers(request.headers);
            headers.set("Authorization", `Bearer ${authStore.accessToken}`);
            return new Request(request, { headers });
        },
        async onResponse({ request, response }) {
            if (response.status !== 401 || request.method === "OPTIONS") {
                return response;
            }
            const pinia = getActivePinia();
            if (!pinia) {
                return response;
            }
            const authStore = useAuthStore(pinia);
            try {
                await authStore.refresh();
            } catch {
                return response;
            }
            if (!authStore.accessToken) {
                return response;
            }
            const headers = new Headers(request.headers);
            headers.set("Authorization", `Bearer ${authStore.accessToken}`);
            return fetch(new Request(request, { headers }));
        },
    });

    // TODO: Adjust based on server limits (maybe this goes in Galaxy config?)
    client.use(
        createRateLimiterMiddleware({
            maxRequests: 100,
            windowMs: 3000,
            retryDelay: 1000,
            maxRetries: 3,
        }),
    );

    return client;
}

export type GalaxyApiClient = ReturnType<typeof apiClientFactory>;

let client: GalaxyApiClient;

/**
 * Returns the Galaxy API client.
 *
 * It can be used to make requests to the Galaxy API using the OpenAPI schema.
 *
 * See: https://openapi-ts.dev/openapi-fetch/
 */
export function GalaxyApi(): GalaxyApiClient {
    if (!client) {
        client = apiClientFactory();
    }

    return client;
}
