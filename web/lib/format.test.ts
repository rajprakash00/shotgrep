import { describe, expect, it } from "vitest";

import { formatClock, formatTimestamp } from "@/lib/format";

describe("formatTimestamp", () => {
  it("renders minutes, seconds, and tenths", () => {
    expect(formatTimestamp(4.44)).toBe("0:04.4");
    expect(formatTimestamp(2)).toBe("0:02.0");
    expect(formatTimestamp(65.25)).toBe("1:05.3");
  });

  it("carries into the next unit when rounding tenths", () => {
    expect(formatTimestamp(59.96)).toBe("1:00.0");
    expect(formatTimestamp(3599.99)).toBe("1:00:00.0");
  });

  it("renders hours once past an hour", () => {
    expect(formatTimestamp(3725.4)).toBe("1:02:05.4");
  });

  it("floors malformed or negative input to zero", () => {
    expect(formatTimestamp(Number.NaN)).toBe("0:00.0");
    expect(formatTimestamp(Number.POSITIVE_INFINITY)).toBe("0:00.0");
    expect(formatTimestamp(-3)).toBe("0:00.0");
  });
});

describe("formatClock", () => {
  it("renders whole seconds", () => {
    expect(formatClock(4.44)).toBe("0:04");
    expect(formatClock(65.9)).toBe("1:05");
    expect(formatClock(3725)).toBe("1:02:05");
  });

  it("floors malformed input to zero", () => {
    expect(formatClock(Number.NaN)).toBe("0:00");
    expect(formatClock(-1)).toBe("0:00");
  });
});
