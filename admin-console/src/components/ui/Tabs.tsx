import * as RadixTabs from "@radix-ui/react-tabs";
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";

import { cn } from "../../lib/utils";

/**
 * Radix supplies the roles, arrow-key navigation and focus handling; these only add the console's look.
 * Inactive panels are unmounted, so keep editable state in the parent (a form object), not in the panels.
 */
export const Tabs = RadixTabs.Root;

export const TabsList = forwardRef<ElementRef<typeof RadixTabs.List>, ComponentPropsWithoutRef<typeof RadixTabs.List>>(
  ({ className, ...props }, ref) => <RadixTabs.List ref={ref} className={cn("tabs__list", className)} {...props} />,
);
TabsList.displayName = "TabsList";

export const TabsTrigger = forwardRef<ElementRef<typeof RadixTabs.Trigger>, ComponentPropsWithoutRef<typeof RadixTabs.Trigger>>(
  ({ className, ...props }, ref) => <RadixTabs.Trigger ref={ref} className={cn("tabs__trigger", className)} {...props} />,
);
TabsTrigger.displayName = "TabsTrigger";

export const TabsContent = forwardRef<ElementRef<typeof RadixTabs.Content>, ComponentPropsWithoutRef<typeof RadixTabs.Content>>(
  ({ className, ...props }, ref) => <RadixTabs.Content ref={ref} className={cn("tabs__panel", className)} {...props} />,
);
TabsContent.displayName = "TabsContent";
