import { Menu } from "@base-ui/react/menu";

import { MoreIcon } from "./icons";

export type MenuAction = {
  label: string;
  onSelect?: () => void;
  disabled?: boolean;
};

export function ActionMenu({
  label,
  actions,
  size = "md",
}: {
  label: string;
  actions: MenuAction[];
  size?: "sm" | "md";
}) {
  return (
    <Menu.Root>
      <Menu.Trigger
        render={
          <button
            type="button"
            className={`action-menu__trigger action-menu__trigger--${size}`}
            aria-label={label}
          />
        }
      >
        <MoreIcon size={16} />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Positioner
          className="action-menu__positioner"
          sideOffset={4}
          align="end"
        >
          <Menu.Popup className="action-menu__popup">
            {actions.map((action) => (
              <Menu.Item
                key={action.label}
                className="action-menu__item"
                disabled={action.disabled}
                onClick={action.onSelect}
              >
                {action.label}
              </Menu.Item>
            ))}
          </Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  );
}
