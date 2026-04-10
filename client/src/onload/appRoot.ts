import { serverPath } from "@/utils/serverPath";

export function getAppRoot(defaultRoot = "/") {
    if (typeof document === "undefined") {
        return defaultRoot;
    }
    const links = document.getElementsByTagName("link");
    const indexLink = Array.from(links).find((link) => link.rel == "index");
    return indexLink && indexLink.href ? serverPath(indexLink.href) : defaultRoot;
}
