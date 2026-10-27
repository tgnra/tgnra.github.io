// Inlined in <head>: runs before first paint.
document.documentElement.className = "js";
// An explicit theme choice (from the nav toggle) overrides the system setting.
try {
  var theme = localStorage.getItem("theme");
  if (theme) document.documentElement.setAttribute("data-theme", theme);
} catch (e) {}
// Slide the other way when going home or back through history.
addEventListener("pagereveal", function (e) {
  if (!e.viewTransition) return;
  var a = window.navigation && navigation.activation;
  var traverseBack = a && a.navigationType === "traverse" && a.from && a.entry &&
      a.entry.index < a.from.index;
  if (location.pathname === "/" || traverseBack) e.viewTransition.types.add("back");
});
