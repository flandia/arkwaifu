import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { cn } from "./cn";

export function Eyebrow({ className, ...props }: ComponentPropsWithoutRef<"p">) {
  return (
    <p
      className={cn(
        "mb-3 font-mono text-[0.72rem] font-bold tracking-[0.12em] uppercase",
        className,
      )}
      {...props}
    />
  );
}

interface SectionHeadingProps extends Omit<ComponentPropsWithoutRef<"div">, "title"> {
  eyebrow?: ReactNode;
  title: ReactNode;
  titleId?: string;
  meta?: ReactNode;
  tone?: "light" | "dark";
}

export function SectionHeading({
  className,
  eyebrow,
  meta,
  title,
  titleId,
  tone = "light",
  ...props
}: SectionHeadingProps) {
  return (
    <div
      className={cn(
        "mb-8 grid grid-cols-[minmax(0,1fr)_auto] items-end border-b-[3px] pb-4",
        tone === "dark" ? "border-white/30" : "border-ink",
        className,
      )}
      {...props}
    >
      {eyebrow ? <Eyebrow className="col-span-full">{eyebrow}</Eyebrow> : null}
      <h2
        className="m-0 max-w-[22ch] text-[clamp(2rem,4vw,4rem)] leading-none font-black tracking-[-0.035em] uppercase"
        id={titleId}
      >
        {title}
      </h2>
      {meta ? <span className="pb-1 font-mono text-sm font-bold tabular-nums">{meta}</span> : null}
    </div>
  );
}
