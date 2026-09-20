import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import ConstraintFields from "@/components/ConstraintFields";
import { emptyConstraints } from "@/lib/constraints";

function Household({ withChildren = false, count = 1 }) {
  const [value, setValue] = useState(() => ({
    ...emptyConstraints(),
    constraints: {
      ...emptyConstraints().constraints,
      children: withChildren,
      family_size: count,
    },
  }));
  return (
    <ConstraintFields
      value={value}
      onNeeds={() => {}}
      onPatch={(patch) =>
        setValue((old) => ({
          ...old,
          constraints: { ...old.constraints, ...patch },
        }))
      }
    />
  );
}
const checked = (name: string) =>
  (screen.getByLabelText(name) as HTMLInputElement).checked;
const people = () =>
  (screen.getByLabelText("Total people, including you") as HTMLInputElement)
    .value;

it("turning Children on and off returns to one person without selecting other members", () => {
  render(<Household />);
  fireEvent.click(screen.getByLabelText("Children"));
  expect(people()).toBe("2");
  fireEvent.click(screen.getByLabelText("Children"));
  expect(checked("Children")).toBe(false);
  expect(checked("Other household members")).toBe(false);
  expect(people()).toBe("1");
});

it("preserves a separately selected household member when Children is unchecked", () => {
  render(<Household />);
  fireEvent.click(screen.getByLabelText("Other household members"));
  fireEvent.click(screen.getByLabelText("Children"));
  expect(people()).toBe("3");
  fireEvent.click(screen.getByLabelText("Children"));
  expect(checked("Other household members")).toBe(true);
  expect(people()).toBe("2");
  fireEvent.click(screen.getByLabelText("Other household members"));
  expect(people()).toBe("1");
});

it("two children do not imply another adult and survive toggling other members", () => {
  render(<Household withChildren count={3} />);
  expect(checked("Other household members")).toBe(false);
  fireEvent.click(screen.getByLabelText("Other household members"));
  expect(people()).toBe("4");
  fireEvent.click(screen.getByLabelText("Other household members"));
  expect(checked("Children")).toBe(true);
  expect(people()).toBe("3");
});
