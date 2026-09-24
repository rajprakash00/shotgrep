import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

const PAPER = "#E6F4DC";
const INK = "#182C18";
const STAMP = "#A8203D";

const INSET = 34;
const ARM = 34;
const STROKE = 17;
const RADIUS = 11;
const DOT = 39;

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          position: "relative",
          display: "flex",
          width: "100%",
          height: "100%",
          background: PAPER,
        }}
      >
        <div
          style={{
            position: "absolute",
            top: INSET,
            left: INSET,
            width: ARM,
            height: ARM,
            borderTop: `${STROKE}px solid ${INK}`,
            borderLeft: `${STROKE}px solid ${INK}`,
            borderTopLeftRadius: RADIUS,
          }}
        />
        <div
          style={{
            position: "absolute",
            top: INSET,
            right: INSET,
            width: ARM,
            height: ARM,
            borderTop: `${STROKE}px solid ${INK}`,
            borderRight: `${STROKE}px solid ${INK}`,
            borderTopRightRadius: RADIUS,
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: INSET,
            left: INSET,
            width: ARM,
            height: ARM,
            borderBottom: `${STROKE}px solid ${INK}`,
            borderLeft: `${STROKE}px solid ${INK}`,
            borderBottomLeftRadius: RADIUS,
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: INSET,
            right: INSET,
            width: ARM,
            height: ARM,
            borderBottom: `${STROKE}px solid ${INK}`,
            borderRight: `${STROKE}px solid ${INK}`,
            borderBottomRightRadius: RADIUS,
          }}
        />
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            width: DOT,
            height: DOT,
            marginTop: -DOT / 2,
            marginLeft: -DOT / 2,
            background: STAMP,
            borderRadius: DOT,
          }}
        />
      </div>
    ),
    size,
  );
}
