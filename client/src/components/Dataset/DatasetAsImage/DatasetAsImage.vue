<script setup lang="ts">
import { computedAsync } from "@vueuse/core";
import { BAlert, BImg } from "bootstrap-vue";
import { computed, ref } from "vue";

import { GalaxyApi } from "@/api/client";
import { withPrefix } from "@/utils/redirect";

interface Props {
    historyDatasetId: string;
    path?: string;
    allowSizeToggle?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    allowSizeToggle: false,
    path: undefined,
});

const imageUrl = computed(() => {
    if (!imageApiUrl.value) {
        return null;
    }
    return withPrefix(imageApiUrl.value);
});

const imageApiUrl = computed(() => {
    if (props.path === undefined || props.path === "undefined") {
        return `/api/datasets/${props.historyDatasetId}/display`;
    }
    return `/api/datasets/${props.historyDatasetId}/display?filename=${props.path}`;
});

const isImage = computedAsync(async () => {
    if (!imageApiUrl.value) {
        return null;
    }
    const { data: buff, error } = await GalaxyApi().GET(imageApiUrl.value as never, {
        parseAs: "blob",
    });
    if (error) {
        return false;
    }
    return buff.type.startsWith("image/");
}, true);

const isFluid = ref(true);

const toggleFluid = () => {
    isFluid.value = !isFluid.value;
};
</script>

<template>
    <div v-if="imageUrl" class="w-100">
        <BAlert v-if="!isImage" variant="warning" show>
            This dataset does not appear to be an image: {{ imageUrl }}.
        </BAlert>
        <button
            v-else
            type="button"
            class="image-wrapper"
            :class="{ interactive: props.allowSizeToggle }"
            @click="props.allowSizeToggle ? toggleFluid() : null">
            <BImg :src="imageUrl" :fluid="isFluid" :class="{ 'cursor-pointer': props.allowSizeToggle }" />
            <div v-if="props.allowSizeToggle" class="size-hint">
                <small class="text-white">{{ isFluid ? "Click for actual size" : "Click to fit width" }}</small>
            </div>
        </button>
    </div>
    <BAlert v-else variant="warning" show>Image not found: {{ imageUrl }}.</BAlert>
</template>

<style lang="scss" scoped>
.image-wrapper {
    background: transparent;
    border: 0;
    padding: 0;
    position: relative;
    display: inline-block;
}

.cursor-pointer {
    cursor: pointer;
    transition: transform 0.2s ease;
}

.interactive .cursor-pointer:hover {
    transform: scale(1.01);
}

.size-hint {
    position: absolute;
    bottom: 8px;
    right: 8px;
    background: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 4px 8px;
    border-radius: 4px;
    opacity: 0;
    transition: opacity 0.2s ease;
    pointer-events: none;

    .image-wrapper:hover & {
        opacity: 1;
    }
}
</style>
