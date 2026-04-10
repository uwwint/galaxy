import { GalaxyApi } from "@/api";
import { rethrowSimple } from "@/utils/simple-error";

export interface Dataset {
    id: string;
    hid: string;
    name: string;
}

export interface DataSource {
    model_class?: string;
    tests: Array<DataSourceTest>;
}

export interface DataSourceTest {
    attr?: string;
    result?: string;
    type?: string;
}

export interface Plugin {
    description: string;
    embeddable?: boolean;
    data_sources?: Array<DataSource>;
    help?: string;
    href: string;
    html: string;
    logo?: string;
    name: string;
    params?: Record<string, ParamType>;
    target?: string;
    tags?: Array<string>;
    tests?: Array<TestType>;
}

export interface ParamType {
    required?: boolean;
}

export interface PluginData {
    hdas: Array<Dataset>;
}

export interface TestParamType {
    ftype?: string;
    label?: string;
    name: string;
    value: string;
}

export interface TestType {
    param: TestParamType;
}

export async function fetchPlugins(datasetId?: string): Promise<Array<Plugin>> {
    try {
        const query = datasetId ? `?dataset_id=${datasetId}` : "";
        const { data, error } = await GalaxyApi().GET("/api/plugins", {
            params: query ? { query: { dataset_id: datasetId } } : undefined,
        });
        if (error) {
            throw error;
        }
        return data;
    } catch (error) {
        rethrowSimple(error);
    }
}

export async function fetchPlugin(id: string): Promise<Plugin> {
    try {
        const { data, error } = await GalaxyApi().GET("/api/plugins/{id}", {
            params: { path: { id } },
        });
        if (error) {
            throw error;
        }
        return data;
    } catch (error) {
        rethrowSimple(error);
    }
}

export async function fetchPluginHistoryItems(id: string, history_id: string): Promise<PluginData> {
    try {
        const { data, error } = await GalaxyApi().GET("/api/plugins/{id}", {
            params: { path: { id }, query: { history_id } },
        });
        if (error) {
            throw error;
        }
        return data;
    } catch (error) {
        rethrowSimple(error);
    }
}
