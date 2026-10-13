// Next.js reescribe el título al navegar: se mantiene el nombre de la plataforma.
(function () {
  var NOMBRE = "Plataforma ISCOUTB";
  function fijar() {
    var t = document.title;
    if (t.indexOf(NOMBRE) === -1) document.title = t.replace(/Dokploy/g, NOMBRE) || NOMBRE;
  }
  fijar();
  new MutationObserver(fijar).observe(document.querySelector("title") || document.head,
    { childList: true, subtree: true, characterData: true });
})();
