import * as HoverCardPrimitive from "@radix-ui/react-hover-card";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export const HoverCard = (props: ComponentProps<typeof HoverCardPrimitive.Root>) => (
  <HoverCardPrimitive.Root openDelay={120} closeDelay={80} {...props} />
);
export const HoverCardTrigger = HoverCardPrimitive.Trigger;

export const HoverCardContent = ({ className, sideOffset = 6, ...props }: ComponentProps<typeof HoverCardPrimitive.Content>) => (
  <HoverCardPrimitive.Portal>
    <HoverCardPrimitive.Content
      sideOffset={sideOffset}
      className={cn("z-50 w-80 rounded-lg border border-line-strong bg-surface p-4 text-sm shadow-xl", className)}
      {...props}
    />
  </HoverCardPrimitive.Portal>
);
