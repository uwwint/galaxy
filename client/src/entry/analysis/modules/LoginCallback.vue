<script setup lang="ts">
import axios from "axios";
import { BAlert, BSpinner } from "bootstrap-vue";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router/composables";

import { useUserStore } from "@/stores/userStore";
import { withPrefix } from "@/utils/redirect";
import { errorMessageAsString } from "@/utils/simple-error";

const router = useRouter();
const userStore = useUserStore();

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
        await axios.post(withPrefix("/auth/bootstrap"));
        userStore.$reset();
        await userStore.loadUser(false);
        window.location.href = withPrefix(getRedirectTarget());
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
