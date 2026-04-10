import { GalaxyApi } from "@/api";
import { rethrowSimple } from "@/utils/simple-error";

import type { CitationsResult } from ".";

export async function getCitations(source: string, id: string): Promise<CitationsResult> {
    try {
        const { data: rawCitations, error } = await GalaxyApi().GET(`/api/${source}/{id}/citations` as never, {
            params: { path: { id } },
        });
        if (error) {
            throw error;
        }
        const citations = [];
        const warnings: string[] = [];
        const { Cite } = await import("./cite");
        for (const rawCitation of rawCitations) {
            if (rawCitation.format === "error") {
                warnings.push(rawCitation.error);
                continue;
            }
            try {
                const cite = new Cite(rawCitation.content);
                citations.push({ raw: rawCitation.content, cite: cite });
            } catch (err) {
                console.warn(`Error parsing bibtex: ${err}`);
            }
        }
        return { citations, warnings };
    } catch (e) {
        rethrowSimple(e);
    }
}
