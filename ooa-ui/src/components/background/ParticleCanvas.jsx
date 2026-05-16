import { useEffect, useRef } from "react";

export default function ParticleCanvas({ motionEnabled, themeName, pointer }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!motionEnabled) return undefined;

    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    const context = canvas.getContext("2d");
    if (!context) return undefined;

    let frameId;
    const particles = Array.from({ length: themeName === "blackbat" ? 90 : 45 }, (_, index) => ({
      id: index,
      x: Math.random(),
      y: Math.random(),
      size: Math.random() * 1.8 + 0.6,
      speed: Math.random() * 0.0008 + 0.0002,
      drift: Math.random() * 0.001 - 0.0005,
    }));

    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = canvas.offsetHeight * window.devicePixelRatio;
    };

    resize();
    window.addEventListener("resize", resize);

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;
      context.clearRect(0, 0, width, height);

      for (const particle of particles) {
        particle.y -= particle.speed;
        particle.x += particle.drift;
        if (particle.y < 0) particle.y = 1;
        if (particle.x < 0 || particle.x > 1) particle.drift *= -1;

        const px = particle.x * width;
        const py = particle.y * height;
        const alpha = themeName === "blackbat" ? 0.55 : 0.35;
        context.fillStyle = `rgba(255,255,255,${alpha})`;
        context.beginPath();
        context.arc(px, py, particle.size * window.devicePixelRatio, 0, Math.PI * 2);
        context.fill();
      }

      if (pointer) {
        context.strokeStyle = themeName === "blackbat"
          ? "rgba(78, 205, 196, 0.35)"
          : "rgba(201, 168, 76, 0.35)";
        context.lineWidth = 2 * window.devicePixelRatio;
        context.beginPath();
        context.moveTo(pointer.x * width, pointer.y * height - 24);
        context.lineTo(pointer.x * width + 36, pointer.y * height + 18);
        context.stroke();
      }

      frameId = window.requestAnimationFrame(render);
    };

    render();
    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("resize", resize);
    };
  }, [motionEnabled, pointer, themeName]);

  return (
    <canvas
      ref={canvasRef}
      className="ooa-bg-canvas"
      aria-hidden="true"
    />
  );
}
