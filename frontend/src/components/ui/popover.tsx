import * as PopoverPrimitive from "@radix-ui/react-popover";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;

export const PopoverContent = ({ className, sideOffset = 6, ...props }: ComponentProps<typeof PopoverPrimitive.Content>) => (
  <PopoverPrimitive.Portal>
    <PopoverPrimitive.Content
      sideOffset={sideOffset}
      className={cn("z-50 w-96 max-w-[90vw] rounded-lg border border-line-strong bg-surface p-4 text-sm shadow-xl", className)}
      {...props}
    />
  </PopoverPrimitive.Portal>
);
