import { GalaxyApi } from "@/api";
import { type Input, permissionInputParts } from "@/composables/datasetPermissions";

export function getPermissionsUrl(historyId: string) {
    return `/history/permissions?id=${historyId}`;
}

export interface PermissionsResponse {
    inputs: Input[];
}

export function getPermissions(historyId: string) {
    return GalaxyApi().GET("/history/permissions" as never, {
        params: { query: { id: historyId } },
    });
}

export function setPermissions(historyId: string, formContents: object) {
    return GalaxyApi().PUT("/history/permissions" as never, {
        params: { query: { id: historyId } },
        body: formContents,
    });
}

export function makePrivate(historyId: string, permissionResponse: PermissionsResponse) {
    const { manageInput } = permissionInputParts(permissionResponse.inputs);
    const managePermissionValue: number = manageInput.value[0] as number;
    const access = [managePermissionValue];
    const formValue = {
        DATASET_MANAGE_PERMISSIONS: [managePermissionValue],
        DATASET_ACCESS: access,
    };
    return setPermissions(historyId, formValue);
}

export async function isHistoryPrivate(permissionResponse: PermissionsResponse) {
    const { accessInput } = permissionInputParts(permissionResponse.inputs);
    return accessInput.value.length >= 1;
}
