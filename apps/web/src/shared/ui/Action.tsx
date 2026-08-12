import type { ButtonHTMLAttributes, ComponentProps } from "react";
import { TransitionLink } from "../../navigation";
import { cn } from "./cn";

type ActionVariant = "primary" | "secondary";
type ActionAdornment = "none" | "forward" | "back" | "external";

const actionVariants: Record<ActionVariant, string> = {
  primary:
    "bg-brand text-brand-ink shadow-hard hover:translate-[0.18rem] hover:bg-brand/95 hover:shadow-hard-sm active:translate-[0.18rem] active:shadow-hard-sm motion-reduce:transform-none",
  secondary: "bg-surface text-ink hover:bg-ink hover:text-surface",
};

const actionBase =
  "inline-flex min-h-13 items-center justify-center gap-6 rounded-none border-2 border-ink px-5 py-3 text-xs font-black tracking-[0.05em] uppercase no-underline transition-[color,background-color,box-shadow,transform] duration-150";

interface ActionStyleProps {
  variant?: ActionVariant;
  adornment?: ActionAdornment;
}

function Adornment({ value }: { value: ActionAdornment }) {
  if (value === "none") return null;
  return <span aria-hidden="true">{value === "back" ? "←" : value === "forward" ? "→" : "↗"}</span>;
}

type ActionLinkProps = ComponentProps<typeof TransitionLink> & ActionStyleProps;

export function ActionLink({
  adornment = "none",
  className,
  variant = "primary",
  ...props
}: ActionLinkProps) {
  return (
    <TransitionLink className={cn(actionBase, actionVariants[variant], className)} {...props}>
      {adornment === "back" ? <Adornment value={adornment} /> : null}
      {props.children}
      {adornment !== "back" ? <Adornment value={adornment} /> : null}
    </TransitionLink>
  );
}

type ActionButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & ActionStyleProps;

export function ActionButton({
  adornment = "none",
  className,
  type = "button",
  variant = "primary",
  ...props
}: ActionButtonProps) {
  return (
    <button className={cn(actionBase, actionVariants[variant], className)} type={type} {...props}>
      {adornment === "back" ? <Adornment value={adornment} /> : null}
      {props.children}
      {adornment !== "back" ? <Adornment value={adornment} /> : null}
    </button>
  );
}
