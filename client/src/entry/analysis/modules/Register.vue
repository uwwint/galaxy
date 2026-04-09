<script setup lang="ts">
import { useConfig } from "@/composables/config";

import RegisterForm from "@/components/Register/RegisterForm.vue";

const { config, isConfigLoaded } = useConfig();
</script>

<template>
    <div class="overflow-auto m-3">
        <RegisterForm
            v-if="isConfigLoaded"
            :disable-local-accounts="config.disable_local_accounts"
            :enable-oidc="config.enable_oidc"
            :mailing-join-addr="config.mailing_join_addr"
            :oidc-idps="config.oidc"
            :prefer-oidc-login="config.prefer_oidc_login"
            :registration-warning-message="config.registration_warning_message"
            :server-mail-configured="config.server_mail_configured"
            :terms-url="config.terms_url" />
    </div>
</template>
