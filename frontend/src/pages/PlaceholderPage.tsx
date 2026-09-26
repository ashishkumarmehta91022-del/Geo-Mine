import { useLocation } from "react-router-dom";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { NAV_ITEMS } from "@/components/layout/navigation";

/**
 * Generic placeholder rendered for every navigation module whose
 * functionality is not implemented yet (Step 1 = shell only).
 */
export default function PlaceholderPage() {
  const { pathname } = useLocation();
  const navItem = NAV_ITEMS.find((item) => item.path === pathname);

  if (!navItem) {
    return (
      <>
        <PageHeader title="Page not found" description={`No route matches "${pathname}".`} />
        <StateBlock
          variant="empty"
          title="Nothing here"
          description="Use the sidebar navigation to reach an existing module."
        />
      </>
    );
  }

  return (
    <>
      <PageHeader title={navItem.label} description={navItem.description} />
      <StateBlock
        variant="empty"
        title="Coming in a later step"
        description="This module is part of the platform roadmap and will be implemented in an upcoming step. See docs/ARCHITECTURE.md for the plan."
      />
    </>
  );
}
