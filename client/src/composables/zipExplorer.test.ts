import { describe, expect, it } from "vitest";

import { useServerMock } from "@/api/client/__mocks__";

import { isRemoteZipFile, isValidUrl } from "./zipExplorer";

const { server, http } = useServerMock();

describe("useZipExplorer", () => {
    describe("isValidUrl", () => {
        it("should return true for valid URLs", () => {
            expect(isValidUrl("http://example.com")).toBe(true);
            expect(isValidUrl("https://example.com")).toBe(true);
        });

        it("should return false for invalid URLs", () => {
            expect(isValidUrl("invalid-url")).toBe(false);
            expect(isValidUrl("htp://example.com")).toBe(false);
        });

        it("should return false for empty strings", () => {
            expect(isValidUrl("")).toBe(false);
        });

        it("should return false for null or undefined values", () => {
            expect(isValidUrl(null)).toBe(false);
            expect(isValidUrl(undefined)).toBe(false);
        });

        it("should return false for multiple URLs", () => {
            expect(isValidUrl("http://example.com\nhttp://example2.com")).toBe(false);
            expect(isValidUrl("https://example.com https://example2.com")).toBe(false);
        });
    });

    describe("isRemoteZipFile", () => {
        it("should detect a remote zip through the Galaxy proxy", async () => {
            server.use(
                http.get("/api/proxy", ({ request }) => {
                    const url = new URL(request.url);
                    expect(url.searchParams.get("url")).toBe("https://example.com/archive.zip");
                    return new Response(new Uint8Array([0x50, 0x4b, 0x03, 0x04]));
                }),
            );

            await expect(isRemoteZipFile("https://example.com/archive.zip")).resolves.toBe(true);
        });

        it("should reject non-zip proxy responses", async () => {
            server.use(
                http.get("/api/proxy", () => {
                    return new Response(new Uint8Array([0x00, 0x01, 0x02, 0x03]));
                }),
            );

            await expect(isRemoteZipFile("https://example.com/not-zip.txt")).resolves.toBe(false);
        });
    });
});
