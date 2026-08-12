import type { ComponentPropsWithoutRef } from "react";
import { cn } from "./cn";

export function ArtworkGrid({ className, ...props }: ComponentPropsWithoutRef<"div">) {
  return (
    <div
      className={cn("grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3", className)}
      {...props}
    />
  );
}
