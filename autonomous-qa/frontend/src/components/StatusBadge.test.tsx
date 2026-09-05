import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import StatusBadge from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders the status text with underscores replaced by spaces", () => {
    render(<StatusBadge status="REVIEW_REQUIRED" />);
    expect(screen.getByText("REVIEW REQUIRED")).toBeInTheDocument();
  });

  it("renders an unknown status without crashing", () => {
    render(<StatusBadge status="SOMETHING_NEW" />);
    expect(screen.getByText("SOMETHING NEW")).toBeInTheDocument();
  });
});
