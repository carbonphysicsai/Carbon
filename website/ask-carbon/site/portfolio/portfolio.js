// The portfolio is complete without JavaScript. Retire old review-page anchors
// without adding a calculator, tracking, storage or remote requests.
const retireOldAnchor = () => {
  if (location.hash === "#economics") {
    const url = new URL(location.href);
    url.hash = "";
    history.replaceState(null, "", url.href);
  }
};
retireOldAnchor();
addEventListener("hashchange", retireOldAnchor);
