<script setup lang="ts">
import { BAlert, BSpinner } from "bootstrap-vue";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router/composables";

import { useAuthStore } from "@/stores/authStore";
import { withPrefix } from "@/utils/redirect";
import { errorMessageAsString } from "@/utils/simple-error";

const router = useRouter();
const authStore = useAuthStore();

const errorMessage = ref<string | null>(null);

function getRedirectTarget(): string {
    const redirect = router.currentRoute.query.redirect;
    if (Array.isArray(redirect)) {
        return redirect[0] || "/";
    }
    return redirect || "/";
}

onMounted(async () => {
    try {
        await authStore.ensureBootstrap();
        await router.replace(withPrefix(getRedirectTarget()));
    } catch (error) {
        errorMessage.value = errorMessageAsString(error, "Login completion failed.");
    }
});
</script>

<template>
    <div class="m-3 text-center">
        <BAlert v-if="errorMessage" show variant="danger">
            {{ errorMessage }}
        </BAlert>
        <div v-else>
            <BSpinner class="mr-2" small />
            Completing login...
        </div>
    </div>
</template>
