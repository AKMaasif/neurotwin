import { useEffect, useRef } from "react";
import * as nav from "./nav";

/** While `open`, the screen has its own browser-history entry: Back closes it (calls onClose) and closing it yourself removes the entry. */
export function useLayer(open: boolean, onClose: () => void) {
  const cb = useRef(onClose); cb.current = onClose;
  useEffect(() => {
    if (!open) return;
    const id = nav.open(() => cb.current());
    return () => nav.close(id);
  }, [open]);
}
