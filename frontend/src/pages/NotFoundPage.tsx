import { Link } from "react-router-dom";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";

/** Polished 404 — the only non-live destination left in the app. */
export default function NotFoundPage() {
  return (
    <>
      <PageHeader
        title="Page not found"
        description="The address does not match any platform module."
      />
      <StateBlock
        variant="empty"
        title="Nothing here"
        description="Use the sidebar navigation to reach an existing module, or return to the dashboard."
        action={<Link to="/dashboard" className="btn-primary">Back to Dashboard</Link>}
      />
    </>
  );
}
