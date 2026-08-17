import { Menu } from "@base-ui/react/menu";

import { ChevronDown, LogoutIcon } from "./icons";

export function SessionMenu({ advisor, workspace, busy, onLogout }: {
  advisor: string;
  workspace: string;
  busy: boolean;
  onLogout: () => void;
}) {
  return (
    <Menu.Root>
      <Menu.Trigger
        render={
          <button
            type="button"
            className="session-menu__trigger"
            aria-label={`Open session menu for ${advisor}`}
          />
        }
      >
        <span className="session-menu__avatar" aria-hidden="true">{advisor.charAt(0).toUpperCase()}</span>
        <span className="session-menu__name">{advisor}</span>
        <ChevronDown className="session-menu__chevron" size={14} aria-hidden="true" />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Positioner className="action-menu__positioner" sideOffset={6} align="end">
          <Menu.Popup className="session-menu__popup">
            <div className="session-menu__identity">
              <strong>{advisor}</strong>
              <small>{workspace}</small>
            </div>
            <Menu.Separator className="session-menu__separator" />
            <Menu.Item
              className="session-menu__item"
              disabled={busy}
              onClick={onLogout}
            >
              <LogoutIcon size={15} aria-hidden="true" />
              {busy ? "Signing out…" : "Sign out"}
            </Menu.Item>
          </Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  );
}
