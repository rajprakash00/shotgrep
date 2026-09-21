import { describe, expect, it } from "vitest";

import { deepLinkPath, parseStartSeconds, searchPath } from "@/lib/urls";

describe("parseStartSeconds", () => {
  it("parses the deep-link timestamp", () => {
    expect(parseStartSeconds("4.44")).toBe(4.44);
    expect(parseStartSeconds("2")).toBe(2);
  });

  it("keeps millisecond precision", () => {
    expect(parseStartSeconds("2.00049")).toBe(2);
    expect(parseStartSeconds("2.0005")).toBe(2.001);
  });

  it("falls back to zero for missing or malformed values", () => {
    expect(parseStartSeconds(null)).toBe(0);
    expect(parseStartSeconds(undefined)).toBe(0);
    expect(parseStartSeconds("")).toBe(0);
    expect(parseStartSeconds("abc")).toBe(0);
    expect(parseStartSeconds("-3")).toBe(0);
    expect(parseStartSeconds("0")).toBe(0);
    expect(parseStartSeconds("Infinity")).toBe(0);
  });

  it("takes the first value when the parameter repeats", () => {
    expect(parseStartSeconds(["5.5", "9"])).toBe(5.5);
  });
});

describe("deepLinkPath", () => {
  it("reduces an absolute deep link to an app path", () => {
    expect(deepLinkPath("http://localhost:3000/watch/abc?t=4.44")).toBe("/watch/abc?t=4.44");
    expect(deepLinkPath("https://shotgrep.example/watch/abc?t=2")).toBe("/watch/abc?t=2");
  });

  it("returns null when the link cannot be parsed", () => {
    expect(deepLinkPath("not a url")).toBeNull();
    expect(deepLinkPath("")).toBeNull();
  });
});

describe("searchPath", () => {
  it("encodes the query", () => {
    expect(searchPath("robotics space")).toBe("/?q=robotics%20space");
    expect(searchPath("  a & b  ")).toBe("/?q=a%20%26%20b");
  });

  it("returns the bare search page for an empty query", () => {
    expect(searchPath("   ")).toBe("/");
  });
});
