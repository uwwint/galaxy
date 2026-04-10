<template>
    <div>
        <div v-if="name">
            <div>
                <div class="header text-center">{{ name }}</div>
            </div>
        </div>
        <LibraryPermissionsWarning :is_admin="is_admin" />
        <hr class="my-4" />
    </div>
</template>

<script>
import { useUserStore } from "@/stores/userStore";

import LibraryPermissionsWarning from "@/components/Libraries/LibraryFolder/LibraryFolderPermissions/LibraryPermissionsWarning.vue";

export default {
    components: {
        LibraryPermissionsWarning,
    },
    props: {
        name: {
            type: String,
            required: true,
        },
    },
    computed: {
        is_admin() {
            return useUserStore().isAdmin;
        },
    },
};
</script>

<style scoped>
.header {
    font-size: 25px;
}
</style>
