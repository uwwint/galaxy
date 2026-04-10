<script lang="ts" setup>
import { faUsers } from "@fortawesome/free-solid-svg-icons";
import { computed, ref } from "vue";

import { GalaxyApi } from "@/api";
import { initRefs, updateRefs, useCallbacks } from "@/composables/datasetPermissions";

import BreadcrumbHeading from "@/components/Common/BreadcrumbHeading.vue";
import DatasetPermissionsForm from "@/components/Dataset/DatasetPermissionsForm.vue";

interface UserDatasetPermissionsProps {
    userId: string;
}
const props = defineProps<UserDatasetPermissionsProps>();

const loading = ref(true);

const {
    managePermissionsOptions,
    accessPermissionsOptions,
    managePermissions,
    accessPermissions,
    simplePermissions,
    checked,
} = initRefs();

const inputsUrl = computed(() => {
    return `/api/users/${props.userId}/permissions/inputs`;
});

async function init() {
    const { data, error } = await GalaxyApi().GET("/api/users/{user_id}/permissions/inputs", {
        params: { path: { user_id: props.userId } },
    });
    if (error) {
        throw error;
    }
    updateRefs(data.inputs, managePermissionsOptions, accessPermissionsOptions, managePermissions, accessPermissions);
    loading.value = false;
}

const title = "Set Dataset Permissions for New Histories";

const breadcrumbItems = [{ title: "User Preferences", to: "/user" }, { title: title }];

const formConfig = computed(() => {
    return {
        title: title,
        id: "edit-preferences-permissions",
        description:
            "Grant others default access to newly created histories. Changes made here will only affect histories created after these settings have been stored.",
        url: inputsUrl.value,
        icon: faUsers,
        submitTitle: "Save Permissions",
        redirect: "/user",
    };
});

async function change(value: unknown) {
    const managePermissionValue: number = managePermissions.value[0] as number;
    let access: number[] = [] as number[];
    if (value) {
        access = [managePermissionValue];
    }
    const formValue = {
        DATASET_MANAGE_PERMISSIONS: [managePermissionValue],
        DATASET_ACCESS: access,
    };
    GalaxyApi()
        .PUT("/api/users/{user_id}/permissions/inputs", {
            params: { path: { user_id: props.userId } },
            body: formValue,
        })
        .then(({ error }) => {
            if (error) {
                throw error;
            }
            onSuccess();
        })
        .catch(onError);
}

const { onSuccess, onError } = useCallbacks(init);
</script>

<template>
    <div>
        <BreadcrumbHeading :items="breadcrumbItems" />

        <DatasetPermissionsForm
            :loading="loading"
            :simple-permissions="simplePermissions"
            :title="title"
            :form-config="formConfig"
            :checked="checked"
            @change="change" />
    </div>
</template>
