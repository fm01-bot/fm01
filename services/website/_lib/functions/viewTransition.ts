/**
 * Sets the origin of the circular "reveal" page transition (see the
 * "Page transitions" section of globals.css). Call it from the click that starts
 * a navigation, before `startTransition(() => { addTransitionType('lang-switch'); ... })`,
 * so the circle grows from under the pointer.
 */
export function setRevealOrigin(clientX: number, clientY: number, control?: Element | null) {
    if (typeof document === "undefined") return;

    // Keyboard activation reports (0, 0): start from the control's centre instead.
    if (!clientX && !clientY && control) {
        const r = control.getBoundingClientRect();
        clientX = r.left + r.width / 2;
        clientY = r.top + r.height / 2;
    }

    // The clip-path runs in the coordinate space of the transition group (the
    // element carrying `data-vt-root`), so convert from viewport coordinates.
    const box = document.querySelector("[data-vt-root]")?.getBoundingClientRect();
    const radius = Math.hypot(
        Math.max(clientX, window.innerWidth - clientX),
        Math.max(clientY, window.innerHeight - clientY),
    );

    const style = document.documentElement.style;
    style.setProperty("--vt-x", `${clientX - (box?.left ?? 0)}px`);
    style.setProperty("--vt-y", `${clientY - (box?.top ?? 0)}px`);
    style.setProperty("--vt-r", `${Math.ceil(radius)}px`);
}
