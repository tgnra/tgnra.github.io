// Inlined in <head>: runs before first paint.
document.documentElement.className = "js";
// Slide the other way when going back through history.
addEventListener("pagereveal", function (e) {
  var a = window.navigation && navigation.activation;
  if (e.viewTransition && a && a.navigationType === "traverse" && a.from && a.entry &&
      a.entry.index < a.from.index) {
    e.viewTransition.types.add("back");
  }
});
