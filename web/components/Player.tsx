"use client";

import { useEffect, useRef } from "react";

export default function Player({
  src,
  startSeconds,
  onMediaError,
}: {
  src: string;
  startSeconds: number;
  onMediaError: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) {
      return;
    }
    const seek = () => {
      video.currentTime = startSeconds;
    };
    seek();
    if (video.readyState < 1) {
      video.addEventListener("loadedmetadata", seek, { once: true });
    }
    return () => video.removeEventListener("loadedmetadata", seek);
  }, [src, startSeconds]);

  return (
    <video
      ref={videoRef}
      src={src}
      controls
      playsInline
      preload="metadata"
      onError={onMediaError}
      className="aspect-video w-full rounded-xl border border-white/10 bg-black"
    />
  );
}
