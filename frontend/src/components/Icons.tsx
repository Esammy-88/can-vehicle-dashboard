// Minimal line icons (24x24, currentColor) for telltales and warnings.
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function Icon({ children, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={20}
      height={20}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export const ArrowLeftIcon = (p: IconProps) => (
  <Icon {...p} fill="currentColor" stroke="none">
    <path d="M10 4 2 12l8 8v-5h12V9H10z" />
  </Icon>
);

export const ArrowRightIcon = (p: IconProps) => (
  <Icon {...p} fill="currentColor" stroke="none">
    <path d="M14 4l8 8-8 8v-5H2V9h12z" />
  </Icon>
);

export const LowBeamIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M13 5c5 0 8 3 8 7s-3 7-8 7z" />
    <path d="M9 7 3 9M9 11 3 13M9 15 3 17" />
  </Icon>
);

export const HighBeamIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M13 5c5 0 8 3 8 7s-3 7-8 7z" />
    <path d="M9 7H3M9 10H3M9 14H3M9 17H3" />
  </Icon>
);

export const SeatbeltIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="4.5" r="2" />
    <path d="M8 21v-7a4 4 0 0 1 8 0v7" />
    <path d="M8.5 10.5 16 19" />
  </Icon>
);

export const DoorIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M7 3h7l3 4v14H7z" />
    <path d="M17 11 22 8" />
    <path d="M10 13h2" />
  </Icon>
);

export const BrakeIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="6" />
    <path d="M4.5 6.5a9 9 0 0 0 0 11M19.5 6.5a9 9 0 0 1 0 11" />
    <path d="M12 9v3.5M12 15h.01" />
  </Icon>
);

export const EngineIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 10v5M3 12.5h2M5 9h3V7h5v2h3l2 2h3v5h-3l-2 2H8l-3-3z" />
  </Icon>
);

export const TemperatureIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3v11" />
    <circle cx="12" cy="17" r="3" />
    <path d="M12 6h3M12 9h3M5 21c2 0 2-1 3.5-1s1.5 1 3.5 1 2-1 3.5-1 1.5 1 3.5 1" />
  </Icon>
);

export const FuelIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 21V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v16M3 21h12M4 10h10" />
    <path d="M14 8h2a2 2 0 0 1 2 2v6a1.5 1.5 0 0 0 3 0V8l-3-3" />
  </Icon>
);

export const GearboxIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1" />
  </Icon>
);

export const AlertTriangleIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3 2 20h20z" />
    <path d="M12 10v4M12 17h.01" />
  </Icon>
);

export const AlertOctagonIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M8 2h8l6 6v8l-6 6H8l-6-6V8z" />
    <path d="M12 7v6M12 16.5h.01" />
  </Icon>
);

export const InfoIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v6M12 7.5h.01" />
  </Icon>
);
