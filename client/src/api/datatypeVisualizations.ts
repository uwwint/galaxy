import { GalaxyApi } from "@/api";
import { rethrowSimple } from "@/utils/simple-error";

/**
 * Interface for datatype to visualization mapping
 */
export interface DatatypeVisualization {
    datatype: string; // Datatype extension (e.g., "h5", "tabular")
    visualization: string; // Visualization plugin name
}

/**
 * Fetches the list of datatype to visualization mappings
 */
export async function fetchDatatypeVisualizations(): Promise<DatatypeVisualization[]> {
    try {
        const { data, error } = await GalaxyApi().GET("/api/datatypes/visualizations");
        if (error) {
            throw error;
        }
        return data;
    } catch (error) {
        rethrowSimple(error);
    }
}

/**
 * Gets the preferred visualization for a specific datatype
 */
export async function getPreferredVisualization(datatype: string): Promise<DatatypeVisualization | null> {
    try {
        const { data, error, response } = await GalaxyApi().GET("/api/datatypes/{datatype}/visualizations", {
            params: { path: { datatype } },
        });
        if (error) {
            if (response?.status === 404) {
                return null;
            }
            throw error;
        }

        // If the API returns an array with one item, return that item
        if (Array.isArray(data) && data.length === 1) {
            return data[0];
        }

        return data;
    } catch (error) {
        rethrowSimple(error);
    }
}
