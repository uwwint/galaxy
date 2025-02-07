<script setup lang="ts">
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import { BButton, BCard } from "bootstrap-vue";
import { computed, onMounted, ref } from "vue";

import { fetcher } from "@/api/schema";
import { useConfigStore } from "@/stores/configurationStore";

import { createTopicUrl, type HelpForumPost, type HelpForumTopic, useHelpURLs } from "./helpForumUrls";

import Heading from "@/components/Common/Heading.vue";
import ExternalLink from "@/components/ExternalLink.vue";

const props = defineProps<{
    toolId: string;
    toolName: string;
}>();

const toolHelpTag = "tool-help";

const helpFetcher = fetcher.path("/api/help/forum/search").method("get").create();

const topics = ref<HelpForumTopic[]>([]);
const posts = ref<HelpForumPost[]>([]);
const helpAvailable = computed(() => topics.value.length > 0);

const root = ref(null);

const query = computed(() => `tags:${props.toolId}+${toolHelpTag} status:solved`);

onMounted(async () => {
    const response = await helpFetcher({ query: query.value });

    const data = response.data;

    topics.value = (data.topics ?? []) as HelpForumTopic[];
    posts.value = data.posts ?? [];
});

const displayCount = 5;

const displayedTopics = computed(() => topics.value.slice(0, displayCount - 1));
const hasMore = computed(() => topics.value.length > displayCount);

function blurbForTopic(topicId: number): string {
    const firstPost = posts.value.find((post) => post.topic_id === topicId);
    return firstPost?.blurb ?? "no content";
}

const { createNewTopicUrl, searchTopicUrl } = useHelpURLs({
    title: computed(() => props.toolName),
    tags: computed(() => [props.toolId, toolHelpTag]),
    query,
});

const configStore = useConfigStore();
</script>

<template>
    <div ref="root" class="tool-help-forum mt-2 mb-4">
        <Heading h2 separator bold size="sm">Help Forum</Heading>

        <p v-if="helpAvailable">
            Following questions on the
            <ExternalLink :href="configStore.config.help_forum_api_url"> Help Forum </ExternalLink> may be related to
            this tool:
        </p>
        <p v-else>
            There are no questions on the
            <ExternalLink :href="configStore.config.help_forum_api_url"> Help Forum </ExternalLink>
            about this tool.
        </p>

        <BCard v-for="topic in displayedTopics" :key="topic.id" class="mb-2">
            <ExternalLink :href="createTopicUrl(topic.id, topic.slug).href">
                <Heading h3 inline size="sm"> {{ topic.title }} </Heading>
            </ExternalLink>
            <p class="mb-0 mt-2">{{ blurbForTopic(topic.id) }}</p>
        </BCard>

        <a v-if="hasMore" :href="searchTopicUrl.href" target="_blank" class="d-block mb-2">Show all...</a>

        <BButton variant="primary" class="font-weight-bold" target="blank" :href="createNewTopicUrl.href">
            <FontAwesomeIcon :icon="['gxd', 'galaxyLogo']" /> Ask a new question
        </BButton>
    </div>
</template>

<style scoped lang="scss">
@import "theme/blue.scss";

.tool-help-forum {
    --fa-secondary-color: #{$brand-toggle};
    --fa-secondary-opacity: 1;
}
</style>
