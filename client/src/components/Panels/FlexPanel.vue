<script setup lang="ts">
import { library } from "@fortawesome/fontawesome-svg-core";
import { faChevronLeft, faChevronRight } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import { useDebounce, useDraggable } from "@vueuse/core";
import { computed, type PropType, ref, watch } from "vue";

import { useTimeoutThrottle } from "@/composables/throttle";

import { determineWidth } from "./utilities";

const { throttle } = useTimeoutThrottle(10);

library.add(faChevronLeft, faChevronRight);

const props = defineProps({
    collapsible: {
        type: Boolean,
        default: true,
    },
    side: {
        type: String as PropType<"left" | "right">,
        default: "right",
    },
});

const minWidth = 200;
const maxWidth = 800;
const defaultWidth = 300;

const draggable = ref<HTMLElement | null>(null);
const root = ref<HTMLElement | null>(null);

const panelWidth = ref(defaultWidth);
const show = ref(true);

const { position, isDragging } = useDraggable(draggable, {
    preventDefault: true,
    exact: true,
});

const hoverDraggable = ref(false);
const hoverDraggableDebounced = useDebounce(hoverDraggable, 100);
const showHover = computed(() => (hoverDraggable.value && hoverDraggableDebounced.value) || isDragging.value);

const showToggle = ref(false);
const hoverToggle = ref(false);
const hoverDraggableOrToggle = computed(
    () => (hoverDraggableDebounced.value || hoverToggle.value) && !isDragging.value
);

const toggleLinger = 1000;
const toggleShowDelay = 100;
let showToggleTimeout: ReturnType<typeof setTimeout> | undefined;

watch(
    () => hoverDraggableOrToggle.value,
    (hover) => {
        clearTimeout(showToggleTimeout);

        if (hover) {
            showToggleTimeout = setTimeout(() => {
                showToggle.value = true;
            }, toggleShowDelay);
        } else {
            showToggleTimeout = setTimeout(() => {
                showToggle.value = false;
            }, toggleLinger);
        }
    }
);

/** Watch position changes and adjust width accordingly */
watch(position, () => {
    throttle(() => {
        if (!root.value || !draggable.value) {
            return;
        }

        const rectRoot = root.value.getBoundingClientRect();
        const rectDraggable = draggable.value.getBoundingClientRect();
        panelWidth.value = determineWidth(rectRoot, rectDraggable, minWidth, maxWidth, props.side, position.value.x);
    });
});

function onKeyLeft() {
    if (props.side === "left") {
        decreaseWidth();
    } else {
        increaseWidth();
    }
}

function onKeyRight() {
    if (props.side === "left") {
        increaseWidth();
    } else {
        decreaseWidth();
    }
}

function increaseWidth(by = 50) {
    panelWidth.value = Math.min(panelWidth.value + by, maxWidth);
}

function decreaseWidth(by = 50) {
    panelWidth.value = Math.max(panelWidth.value - by, minWidth);
}

const sideClasses = computed(() => ({
    left: props.side === "left",
    right: props.side === "right",
}));
</script>

<template>
    <div
        v-if="show"
        :id="side"
        ref="root"
        class="flex-panel"
        :class="{ ...sideClasses, 'show-hover': showHover }"
        :style="`--width: ${panelWidth}px`">
        <button
            ref="draggable"
            class="drag-handle"
            @mouseenter="hoverDraggable = true"
            @focusin="hoverDraggable = true"
            @mouseout="hoverDraggable = false"
            @focusout="hoverDraggable = false"
            @keydown.left="onKeyLeft"
            @keydown.right="onKeyRight">
            <span class="sr-only"> Side panel drag handle </span>
        </button>

        <button
            v-if="props.collapsible"
            class="collapse-button open"
            :class="{ ...sideClasses, show: showToggle }"
            title="Close panel"
            @click="show = false"
            @mouseenter="hoverToggle = true"
            @focusin="hoverToggle = true"
            @mouseout="hoverToggle = false"
            @focusout="hoverToggle = false">
            <FontAwesomeIcon v-if="side === 'left'" fixed-width icon="fa-chevron-left" />
            <FontAwesomeIcon v-else icon="fa-chevron-right" fixed-width />
        </button>

        <slot />

        <div v-if="isDragging" class="interaction-overlay" />
    </div>
    <div v-else>
        <button
            class="collapse-button closed"
            :class="{ ...sideClasses, show: true }"
            title="Open panel"
            @click="
                show = true;
                hoverToggle = false;
            ">
            <FontAwesomeIcon v-if="side === 'right'" fixed-width icon="fa-chevron-left" />
            <FontAwesomeIcon v-else icon="fa-chevron-right" fixed-width />
        </button>
    </div>
</template>

<style scoped lang="scss">
@import "theme/blue.scss";

.flex-panel {
    z-index: 100;
    flex-shrink: 0;
    display: flex;
    width: var(--width);
    position: relative;
    border-color: $border-color;
    border-width: 1px;
    box-shadow: 1px 0 transparent;
    transition: border-color 0.1s, box-shadow 0.1s;
    align-items: stretch;
    flex-direction: column;

    &.show-hover {
        border-color: $brand-info;

        &.left {
            box-shadow: 1px 0 $brand-info;
        }

        &.right {
            box-shadow: -1px 0 $brand-info;
        }
    }

    &.left {
        border-right-style: solid;

        .drag-handle {
            right: -0.75rem;
        }
    }

    &.right {
        border-left-style: solid;

        .drag-handle {
            left: -0.75rem;
        }
    }
}

.drag-handle {
    background: none;
    border: none;
    position: absolute;
    width: 1rem;
    padding: 0;
    height: 100%;

    &:hover {
        cursor: ew-resize;
    }
}

.collapse-button {
    position: absolute;
    z-index: 100;

    --width: 0px;

    width: var(--width);
    overflow: hidden;

    transition: width 0.1s, left 0.1s, right 0.1s;
    border-style: none;

    &:hover,
    &.show,
    &:focus {
        --width: 1.5rem;
        border-style: solid;
    }

    height: 4rem;
    top: calc(50% - 2rem);
    padding: 0;
    display: grid;
    place-items: center;

    &.left {
        right: calc(var(--width) * -1);
        border-top-left-radius: 0;
        border-bottom-left-radius: 0;
    }

    &.right {
        left: calc(var(--width) * -1);
        border-top-right-radius: 0;
        border-bottom-right-radius: 0;
    }

    &.closed {
        --width: 0.75rem;
        border-style: solid;

        > * {
            transform: translateX(-0.15rem);
        }

        &:hover,
        &:focus {
            --width: 1.5rem;
        }

        &.right {
            left: unset;
            right: 0;
        }

        &.left {
            right: unset;
            left: 0;
        }
    }
}

.interaction-overlay {
    height: 100%;
    position: fixed;
    left: 0;
    width: 100%;
    cursor: ew-resize;
}
</style>
