<script setup lang="ts">
import { ref, watch } from "vue";

import { GalaxyApi } from "@/api";

const props = defineProps<{
    invocationId: string;
}>();

const invocationTime = ref();

async function fetchInvocation(invocationId: string) {
    try {
        const { data, error } = await GalaxyApi().GET("/api/invocations/{invocation_id}", {
            params: { path: { invocation_id: invocationId } },
        });
        if (error) {
            throw error;
        }
        if (data.create_time) {
            invocationTime.value = new Date(data.create_time).toUTCString();
        }
    } catch (error) {
        console.error("Error fetching invocation time:", error);
        invocationTime.value = "";
    }
}

watch(
    () => props.invocationId,
    () => fetchInvocation(props.invocationId),
    { immediate: true },
);
</script>

<template>
    <div class="invocation-time">
        <pre class="m-0">{{ invocationTime }}</pre>
    </div>
</template>
