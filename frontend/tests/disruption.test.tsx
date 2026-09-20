import { useState } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import DisruptionInput, { type ChangeMessage } from "@/components/DisruptionInput";

it("dismisses only the hint and keeps change history across closing, busy updates, and reopening", () => {
  const submit = vi.fn();
  function Widget({ messages, busy = false }: { messages: ChangeMessage[]; busy?: boolean }) {
    const [open, setOpen] = useState(false);
    return <DisruptionInput open={open} onOpenChange={setOpen} onSubmit={submit} busy={busy} messages={messages} />;
  }
  const view = render(<Widget messages={[]} />);
  fireEvent.click(screen.getByRole("button", { name: "Dismiss Something changed hint" }));
  expect(screen.queryByText("Something changed?")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Something changed? Open changes panel" }));
  const input = screen.getByLabelText("What changed");
  expect(document.activeElement).toBe(input);
  fireEvent.change(input, { target: { value: "I lost my wallet" } });
  fireEvent.submit(input.closest("form")!);
  expect(submit).toHaveBeenCalledWith("I lost my wallet");
  const messages: ChangeMessage[] = [{ role: "user", text: "I lost my wallet" }];
  view.rerender(<Widget messages={messages} busy />);
  expect(screen.getByText("Checking your plan…")).toBeTruthy();
  view.rerender(<Widget messages={[...messages, { role: "assistant", text: "Your route was updated." }]} />);
  fireEvent.keyDown(screen.getByLabelText("What changed"), { key: "Escape" });
  expect(screen.queryByRole("log")).toBeNull();
  expect(screen.queryByRole("button", { name: "Dismiss Something changed hint" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Something changed? Open changes panel" }));
  const log = within(screen.getByRole("log"));
  expect(log.getByText("I lost my wallet")).toBeTruthy();
  expect(log.getByText("Your route was updated.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "I missed the bus" }));
  expect(submit).toHaveBeenLastCalledWith("I missed the bus");
});
