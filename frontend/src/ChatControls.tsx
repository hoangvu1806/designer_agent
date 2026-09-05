import { Check, ChevronDown, Monitor, MonitorSmartphone, Smartphone, Tablet } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export const STARTER_PROMPTS = [
  {
    title: "Analytics Dashboard",
    prompt: "Design a modern SaaS analytics dashboard with KPI metric cards, revenue growth chart, and recent transaction list.",
    screenName: "Analytics Overview",
    platform: "desktop",
  },
  {
    title: "E-Commerce Checkout",
    prompt: "Design a streamlined 2-column e-commerce checkout page with order summary, shipping address form, and payment methods.",
    screenName: "Checkout Flow",
    platform: "responsive",
  },
  {
    title: "Mobile Authentication",
    prompt: "Design an iOS mobile login and registration screen with social sign-in (Apple, Google), biometric toggle, and clean inputs.",
    screenName: "Mobile Sign In",
    platform: "mobile",
  },
  {
    title: "Team & Billing Settings",
    prompt: "Design an account settings page with subscription plan tier switcher, team member permission table, and invoice history.",
    screenName: "Billing & Team",
    platform: "desktop",
  },
] as const;

const PLATFORMS = [
  { value: "responsive", label: "Responsive", icon: MonitorSmartphone },
  { value: "desktop", label: "Desktop", icon: Monitor },
  { value: "tablet", label: "Tablet", icon: Tablet },
  { value: "mobile", label: "Mobile", icon: Smartphone },
];

export function PlatformSelector({
  value, onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = PLATFORMS.find((item) => item.value === value) || PLATFORMS[0];
  const Icon = current.icon;

  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    const closeKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", closeOutside);
    document.addEventListener("keydown", closeKey);
    return () => {
      document.removeEventListener("mousedown", closeOutside);
      document.removeEventListener("keydown", closeKey);
    };
  }, [open]);

  return (
    <div className="custom-dropdown-container" ref={ref}>
      <button
        type="button"
        className={`composer-mini-pill dropdown-trigger ${open ? "active" : ""}`}
        onClick={() => setOpen(!open)}
        title="Select target viewport platform"
      >
        <Icon size={13} style={{ color: "var(--violet)" }} />
        <span>{current.label}</span>
        <ChevronDown size={12} className={`dropdown-chevron ${open ? "rotate" : ""}`} />
      </button>
      {open && (
        <div className="custom-dropdown-menu" role="menu">
          {PLATFORMS.map(({ value: option, label, icon: OptionIcon }) => (
            <button
              key={option}
              type="button"
              className={`custom-dropdown-item ${option === value ? "selected" : ""}`}
              onClick={() => { onChange(option); setOpen(false); }}
              role="menuitem"
            >
              <OptionIcon size={14} /><span>{label}</span>
              {option === value && <Check size={13} className="check-icon" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

