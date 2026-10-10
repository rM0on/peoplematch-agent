import { render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { cleanup } from "@testing-library/react";
import { AppSidebar } from "./app-sidebar";

afterEach(cleanup);

it("links to frozen offline evaluation without implying production results", () => {
  render(<AppSidebar active="evaluation" />);
  expect(screen.getByRole("link", { name: "离线评估" }).getAttribute("href")).toBe("/evaluation");
});
