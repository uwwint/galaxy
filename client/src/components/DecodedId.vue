<template>
    <span v-if="decoded_id">({{ decoded_id }})</span>
</template>
<script>
import { GalaxyApi } from "@/api/client";
import { getGalaxyInstance } from "@/app";
import { useUserStore } from "@/stores/userStore";
import { rethrowSimple } from "@/utils/simple-error";

export default {
    props: {
        id: {
            type: String,
            required: true,
        },
    },
    data() {
        return { decoded_id: null };
    },
    computed: {
        isAdmin() {
            // window.parent.Galaxy is needed when instance is mounted in mako
            const userStore = useUserStore();
            const galaxy = getGalaxyInstance() || window.parent.Galaxy;
            return userStore.isAdmin || galaxy?.user?.isAdmin() || false;
        },
    },
    created: function () {
        this.decodeId(this.id);
    },
    methods: {
        decodeId: async function (id) {
            if (this.isAdmin) {
                try {
                    const { data } = await GalaxyApi().GET("/api/configuration/decode/{id}", {
                        params: { path: { id } },
                    });
                    this.decoded_id = data.decoded_id;
                } catch (e) {
                    rethrowSimple(e);
                }
            }
        },
    },
};
</script>
