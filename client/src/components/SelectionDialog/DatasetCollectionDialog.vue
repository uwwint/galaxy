<script setup lang="ts">
import { onMounted, ref } from "vue";

import { GalaxyApi } from "@/api/client";
import type { SelectionItem } from "@/components/SelectionDialog/selectionTypes";
import { errorMessageAsString } from "@/utils/simple-error";

import SelectionDialog from "@/components/SelectionDialog/SelectionDialog.vue";

interface HistoryItem {
    id: string;
    name: string;
    created_time: string;
    hid: number;
    collection_type?: string;
}

interface Props {
    callback?: (results: SelectionItem) => void;
    history: string;
    collectionTypes?: string[];
}

const props = withDefaults(defineProps<Props>(), {
    callback: () => {},
});

const emit = defineEmits<{
    (e: "onCancel"): void;
    (e: "onOk", results: SelectionItem): void;
    (e: "onUpload"): void;
}>();

const errorMessage = ref("");
const items = ref([]);
const modalShow = ref(true);
const optionsShow = ref(false);

function onClick(record: SelectionItem) {
    modalShow.value = false;
    props.callback(record);
    emit("onOk", record);
}

/** Called when the modal is hidden */
function onCancel() {
    modalShow.value = false;
    emit("onCancel");
}

/** Performs server request to retrieve data records **/
function load() {
    optionsShow.value = false;
    GalaxyApi()
        .GET("/api/histories/{history_id}/contents", {
            params: {
                path: { history_id: props.history },
                query: { type: "dataset_collection" },
            },
        })
        .then(({ data }) => {
            let collection_instances = data.sort((a: HistoryItem, b: HistoryItem) => b.hid - a.hid);
            if (props.collectionTypes?.length) {
                collection_instances = collection_instances.filter(
                    (item: HistoryItem) =>
                        item.collection_type && props.collectionTypes!.includes(item.collection_type),
                );
            }
            items.value = collection_instances.map((item: HistoryItem) => {
                return {
                    id: item.id,
                    label: item.name,
                    time: item.created_time,
                    isLeaf: true,
                };
            });
            optionsShow.value = true;
        })
        .catch((error) => {
            errorMessage.value = errorMessageAsString(error);
        });
}

onMounted(() => {
    load();
});
</script>

<template>
    <SelectionDialog
        :error-message="errorMessage"
        :options-show="optionsShow"
        :modal-show="modalShow"
        leaf-icon="fa fa-folder"
        :items="items"
        @onCancel="onCancel"
        @onClick="onClick" />
</template>
