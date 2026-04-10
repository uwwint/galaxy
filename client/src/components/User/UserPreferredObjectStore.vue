<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed, ref } from "vue";

import { GalaxyApi, isRegisteredUser } from "@/api";
import { useConfigStore } from "@/stores/configurationStore";
import { useUserStore } from "@/stores/userStore";
import { errorMessageAsString } from "@/utils/simple-error";

import GModal from "../BaseComponents/GModal.vue";
import SelectObjectStore from "@/components/ObjectStore/SelectObjectStore.vue";

const emit = defineEmits<{
    (e: "reset"): void;
}>();

const userStore = useUserStore();
const { currentUser } = storeToRefs(userStore);

const { isLoaded: isConfigLoaded, config } = storeToRefs(useConfigStore());

const error = ref();
const selectedObjectStoreId = ref(
    isRegisteredUser(currentUser.value) ? (currentUser.value?.preferred_object_store_id ?? null) : null,
);

const title = computed(() => {
    return `${preferredOrEmptyString.value} Galaxy Storage`;
});
const preferredOrEmptyString = computed(() => {
    if (isConfigLoaded && config.value?.object_store_always_respect_user_selection) {
        return "";
    } else {
        return "Preferred";
    }
});

function resetModal() {
    error.value = null;
    emit("reset");
}

async function handleSubmit(preferred: string | null) {
    const payload = { preferred_object_store_id: preferred };

    try {
        const { error } = await GalaxyApi().PUT("/api/users/current", {
            body: payload,
        });
        if (error) {
            throw error;
        }

        selectedObjectStoreId.value = preferred;
    } catch (e) {
        error.value = errorMessageAsString(e);
    }
}
</script>

<template>
    <GModal id="modal-select-preferred-object-store" :title="title" show size="medium" @close="resetModal">
        <SelectObjectStore
            :parent-error="error"
            :selected-object-store-id="selectedObjectStoreId"
            for-what="New dataset outputs from tools and workflows"
            default-option-title="Galaxy Defaults"
            default-option-description="Selecting this will reset Galaxy to default behaviors configured by your Galaxy administrator."
            @onSubmit="handleSubmit" />
    </GModal>
</template>
