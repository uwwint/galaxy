<script setup lang="ts">
import { storeToRefs } from "pinia";
import { nextTick, watch } from "vue";

import { FAVORITES_KEYS, searchTools } from "@/components/Panels/utilities";
import type { Tool, ToolPanelItem, ToolSection } from "@/stores/toolStore";
import { useUserStore } from "@/stores/userStore";
import _l from "@/utils/localization";

import DelayedInput from "@/components/Common/DelayedInput.vue";

const MIN_QUERY_LENGTH = 3;

interface Props {
    currentPanelView: string;
    placeholder?: string;
    query?: string | null;
    queryPending?: boolean;
    toolsList: Tool[];
    currentPanel: Record<string, ToolPanelItem>;
    useWorker?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    placeholder: "search tools",
    query: null,
    queryPending: false,
    useWorker: false,
});

const emit = defineEmits<{
    (
        e: "onResults",
        filtered: string[] | null,
        sectioned: Record<string, Tool | ToolSection> | null,
        closestValue: string | null,
    ): void;
    (e: "onQuery", query: string): void;
}>();

const { currentFavorites } = storeToRefs(useUserStore());

interface RequestPayload {
    tools: Tool[];
    query: string;
    currentPanel: Record<string, ToolPanelItem>;
}

interface SearchEventQuery {
    type: "searchTools";
    payload: RequestPayload;
}

interface SearchEventClear {
    type: "clearFilter";
}

interface SearchEventFavorite {
    type: "favoriteTools";
}

type SearchEventData = SearchEventQuery | SearchEventClear | SearchEventFavorite;

interface SearchEvent {
    data: SearchEventData;
}

interface ResponsePayloadResults {
    type: "searchToolsByKeysResult";
    payload: string[];
    query: string;
    closestTerm: string | null;
    sectioned: Record<string, Tool | ToolSection> | null;
}

interface ResponseClearFilter {
    type: "clearFilterResult";
}

interface ResponseFavoriteTools {
    type: "favoriteToolsResult";
}

type ResponsePayloadData = ResponsePayloadResults | ResponseClearFilter | ResponseFavoriteTools;

interface ResponsePayload {
    type: "message";
    data: ResponsePayloadData;
}

function handlePost(event: SearchEvent) {
    const { type } = event.data;
    if (type === "searchTools") {
        const { tools, query, currentPanel } = event.data.payload;
        const { results, resultPanel, closestTerm } = searchTools(tools, query, currentPanel);
        // send the result back to the main thread
        onMessage({
            data: {
                type: "searchToolsByKeysResult",
                payload: results.slice(),
                sectioned: resultPanel,
                query: query,
                closestTerm: closestTerm,
            },
        } as unknown as MessageEvent);
    } else if (type === "clearFilter") {
        onMessage({ data: { type: "clearFilterResult" } } as unknown as MessageEvent);
    } else if (type === "favoriteTools") {
        onMessage({ data: { type: "favoriteToolsResult" } } as unknown as MessageEvent);
    }
}

function onMessage(event: MessageEvent) {
    const type = (event as unknown as ResponsePayload).data.type;
    if (type === "searchToolsByKeysResult") {
        const data = event.data as ResponsePayloadResults;
        const { payload, sectioned, query, closestTerm } = data;
        if (query === props.query) {
            emit("onResults", payload, sectioned, closestTerm);
        }
    } else if (type === "clearFilterResult") {
        emit("onResults", null, null, null);
    } else if (type === "favoriteToolsResult") {
        emit("onResults", currentFavorites.value.tools, null, null);
    }
}

watch(
    () => currentFavorites.value.tools,
    () => {
        if (FAVORITES_KEYS.includes(props.query)) {
            post({ type: "favoriteTools" });
        }
    },
);

function checkQuery(q: string) {
    emit("onQuery", q);
    if (q.trim() && q.trim().length >= MIN_QUERY_LENGTH) {
        if (FAVORITES_KEYS.includes(q)) {
            post({ type: "favoriteTools" });
        } else {
            post({
                type: "searchTools",
                payload: {
                    tools: props.toolsList,
                    query: q,
                    currentPanel: props.currentPanel,
                },
            });
        }
    } else {
        post({ type: "clearFilter" });
    }
}

function post(message: object) {
    nextTick(() => {
        handlePost({ data: message as SearchEventData });
    });
}
</script>

<template>
    <div>
        <DelayedInput
            class="mb-3"
            :value="props.query"
            :delay="200"
            :loading="queryPending"
            :placeholder="placeholder"
            @change="checkQuery" />
    </div>
</template>
