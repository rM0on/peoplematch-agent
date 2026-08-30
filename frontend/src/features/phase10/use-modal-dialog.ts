"use client";

import { type KeyboardEvent, useLayoutEffect, useRef } from "react";


const focusableSelector = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function focusableChildren(container: HTMLElement) {
  return Array.from(container.querySelectorAll<HTMLElement>(focusableSelector))
    .filter((element) => !element.hidden && element.getAttribute("aria-hidden") !== "true");
}

export function useModalDialog(open: boolean, onClose: () => void) {
  const dialogRef = useRef<HTMLElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const openRef = useRef(open);

  useLayoutEffect(() => {
    openRef.current = open;
  }, [open]);

  useLayoutEffect(() => {
    if (!open) return;
    returnFocusRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    focusableChildren(dialogRef.current ?? document.body)[0]?.focus();
    return () => {
      const returnTarget = returnFocusRef.current;
      queueMicrotask(() => {
        if (openRef.current) return;
        if (returnTarget?.isConnected) {
          returnTarget.focus();
          return;
        }
        document.querySelector<HTMLElement>("[data-modal-focus-fallback]")?.focus();
      });
    };
  }, [open]);

  function onDialogKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !dialogRef.current) return;
    const focusable = focusableChildren(dialogRef.current);
    if (!focusable.length) {
      event.preventDefault();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && (active === first || !dialogRef.current.contains(active))) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && (active === last || !dialogRef.current.contains(active))) {
      event.preventDefault();
      first.focus();
    }
  }

  return { dialogRef, onDialogKeyDown };
}
