"use client";

import { useEffect, useRef } from "react";

interface WaveformProps {
  src: string;
  height?: number;
  color?: string;
}

export default function Waveform({
  src,
  height = 100,
  color = "#007bff",
}: WaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Generate a simple waveform visualization with random bars
    // In a production app, this would analyze the actual audio
    const barCount = 100;
    const bars: number[] = [];

    for (let i = 0; i < barCount; i++) {
      const randomHeight = Math.random() * 0.8 + 0.2;
      bars.push(randomHeight);
    }

    // Clear canvas
    ctx.fillStyle = "#f9f9f9";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw waveform
    const barWidth = canvas.width / barCount;
    ctx.fillStyle = color;

    bars.forEach((bar, i) => {
      const barHeight = bar * height;
      const y = (height - barHeight) / 2;
      ctx.fillRect(i * barWidth + 1, y, barWidth - 2, barHeight);
    });
  }, [height, color]);

  return (
    <canvas
      ref={canvasRef}
      width={600}
      height={height}
      style={{ border: "1px solid #ddd", borderRadius: "4px" }}
    />
  );
}
