<template>
    <GButton
        v-if="isConfigLoaded && canDownload(config)"
        tooltip
        tooltip-placement="bottom"
        :title="title"
        :color="color"
        :outline="outline"
        :size="size"
        @click="onDownload(config)">
        Generate
        <FontAwesomeIcon v-if="waiting" :icon="faSpinner" spin />
        <FontAwesomeIcon v-else :icon="faDownload" />
    </GButton>
</template>

<script>
/*
    A Galaxy Button with logic for interfacing with Galaxy's short term storage
    component (STS).
*/
import { faDownload, faSpinner } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";

import { GalaxyApi } from "@/api/client";
import { useConfig } from "@/composables/config";
import { Toast } from "@/composables/toast";
import { withPrefix } from "@/utils/redirect";

import GButton from "./BaseComponents/GButton.vue";

export default {
    components: {
        FontAwesomeIcon,
        GButton,
    },
    props: {
        title: {
            type: String,
            required: true,
        },
        downloadEndpoint: {
            type: String,
            required: true,
        },
        postParameters: {
            type: Object,
            default: () => {
                return {};
            },
        },
        fallbackUrl: {
            type: String,
            default: null,
        },
        color: {
            type: String,
            default: null,
        },
        outline: {
            type: Boolean,
            default: false,
        },
        size: {
            type: String,
            default: "medium",
        },
    },
    setup() {
        const { config, isConfigLoaded } = useConfig(true);
        return { config, isConfigLoaded };
    },
    data() {
        return {
            faDownload,
            faSpinner,
            waiting: false,
            delay: 200,
        };
    },
    destroyed() {
        this.clearTimeout();
    },
    methods: {
        canDownload(config) {
            if (!config.enable_celery_tasks) {
                return this.fallbackUrl != null;
            }
            return true;
        },
        onDownload(config) {
            if (!config.enable_celery_tasks) {
                window.open(withPrefix(this.fallbackUrl));
            } else {
                this.waiting = true;
                GalaxyApi()
                    .POST(this.downloadEndpoint, {
                        body: this.postParameters,
                    })
                    .then(this.handleInitialize)
                    .catch(this.handleError);
            }
        },
        handleInitialize(response) {
            const storageRequestId = response.data.storage_request_id;
            this.pollStorageRequestId(storageRequestId);
        },
        pollStorageRequestId(storageRequestId) {
            GalaxyApi()
                .GET("/api/short_term_storage/{storage_request_id}/ready", {
                    params: { path: { storage_request_id: storageRequestId } },
                })
                .then((r) => {
                    this.handlePollResponse(r, storageRequestId);
                })
                .catch(this.handleError);
        },
        handlePollResponse(response, storageRequestId) {
            const ready = response.data;
            if (ready) {
                window.location.assign(`/api/short_term_storage/${storageRequestId}`);
                this.waiting = false;
            } else {
                this.pollAfterDelay(storageRequestId);
            }
        },
        handleError(err) {
            Toast.error(`Failed to generate download: ${err}`);
            this.waiting = false;
        },
        clearTimeout() {
            if (this.timeout) {
                clearTimeout(this.timeout);
            }
        },
        pollAfterDelay(storageRequestId) {
            this.clearTimeout();
            this.timeout = setTimeout(() => {
                this.pollStorageRequestId(storageRequestId);
            }, this.delay);
        },
    },
};
</script>
