import * as TabsPrimitive from "@radix-ui/react-tabs";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export const Tabs = TabsPrimitive.Root;

export const TabsList = ({ className, ...props }: ComponentProps<typeof TabsPrimitive.List>) => (
  <TabsPrimitive.List className={cn("inline-flex items-center gap-1 rounded-full border border-line bg-surface p-1", className)} {...props} />
);

export const TabsTrigger = ({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) => (
  <TabsPrimitive.Trigger
    className={cn(
      "inline-flex h-8 items-center gap-2 rounded-full px-4 text-sm font-bold text-ink-2 transition-colors cursor-pointer",
      "hover:text-ink data-[state=active]:bg-brand data-[state=active]:text-white [&_svg]:size-4",
      className,
    )}
    {...props}
  />
);

export const TabsContent = ({ className, ...props }: ComponentProps<typeof TabsPrimitive.Content>) => (
  <TabsPrimitive.Content className={cn("mt-6 focus-visible:outline-none", className)} {...props} />
);
