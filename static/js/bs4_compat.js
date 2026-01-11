(function () {
  function copyAttr(el, from, to) {
    var v = el.getAttribute(from);
    if (v && !el.getAttribute(to)) {
      el.setAttribute(to, v);
    }
  }

  function migrateDataBsAttributes(root) {
    var nodes = root.querySelectorAll('[data-bs-toggle], [data-bs-target], [data-bs-dismiss]');
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      copyAttr(el, 'data-bs-toggle', 'data-toggle');
      copyAttr(el, 'data-bs-target', 'data-target');
      copyAttr(el, 'data-bs-dismiss', 'data-dismiss');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      migrateDataBsAttributes(document);
    });
  } else {
    migrateDataBsAttributes(document);
  }
})();

