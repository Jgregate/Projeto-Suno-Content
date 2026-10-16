import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export const Card = ({ className, ...props }: ComponentProps<"div">) => (
  <div className={cn("rounded-lg border border-line bg-surface shadow-[0_1px_2px_rgb(0_0_0/0.04)]", className)} {...props} />
);

export const CardHeader = ({ className, ...props }: ComponentProps<"div">) => (
  <div className={cn("flex flex-col gap-1 px-5 pt-5", className)} {...props} />
);

export const CardTitle = ({ className, ...props }: ComponentProps<"h3">) => (
  <h3 className={cn("font-serif text-lg font-semibold tracking-tight", className)} {...props} />
);

export const CardBody = ({ className, ...props }: ComponentProps<"div">) => (
  <div className={cn("px-5 pb-5 pt-3", className)} {...props} />
);
