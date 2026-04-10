import { GalaxyApi } from "@/api";
import { rethrowSimple } from "@/utils/simple-error";

export async function submitData(url, payload) {
    try {
        const { data, error } = await GalaxyApi().PUT(url, {
            body: payload,
        });
        if (error) {
            throw error;
        }
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}
