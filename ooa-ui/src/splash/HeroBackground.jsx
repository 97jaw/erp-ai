export default function HeroBackground({ variant = "dark" }) {
  const usePhoto = variant === "dark";

  return (
    <div
      className={`splash-hero splash-hero--${variant}`}
      style={
        usePhoto
          ? {
              backgroundImage:
                "linear-gradient(160deg, rgba(26,39,68,0.85) 0%, rgba(10,15,30,0.92) 100%), radial-gradient(ellipse at 70% 20%, rgba(201,168,76,0.25) 0%, transparent 50%)",
            }
          : undefined
      }
      aria-hidden="true"
    >
      <div className="splash-hero__overlay" />
    </div>
  );
}
