// Marca del panel de Dokploy. Todo es idempotente y tolera que React vuelva a pintar.
(function () {
  var NOMBRE = "Plataforma ISCOUTB";

  function titulo() {
    var t = document.title;
    if (t.indexOf(NOMBRE) === -1) document.title = t.replace(/Dokploy/g, NOMBRE) || NOMBRE;
  }

  function texto(el, valor) { if (el && el.textContent !== valor) el.textContent = valor; }

  function login() {
    var form = document.getElementById("login-form");
    document.body.classList.toggle("marca-login", !!form);
    if (!form) return;

    // Panel izquierdo: nombre en lugar del logo de Dokploy y mensaje de bienvenida
    var enlace = document.querySelector('a[href="/"]');
    if (enlace && !enlace.querySelector(".marca-nombre")) {
      var svg = enlace.querySelector("svg");
      enlace.textContent = "";
      if (svg) enlace.appendChild(svg);
      enlace.insertAdjacentHTML("beforeend",
        '<span><span class="marca-nombre">ISCOUTB</span>' +
        '<span class="marca-sub">Universidad Tecnológica de Bolívar</span></span>');
    }
    var cita = document.querySelector("blockquote p");
    texto(cita, "Plataforma de despliegue de proyectos del programa de Ingeniería de Sistemas y Computación " +
                "de la Universidad Tecnológica de Bolívar. Ingresa con tu correo institucional @utb.edu.co.");

    // Formulario
    var h1 = document.querySelector("h1");
    if (h1 && h1.lastChild && h1.querySelector("div")) {
      var cont = h1.querySelector("div");
      var nodo = cont.lastChild;
      if (nodo && nodo.nodeType === 3) texto(nodo, "Plataforma ISCOUTB");
    }
    // Novedades: tarjeta destacada encima del título del formulario
    var cab = h1 && h1.parentElement;
    if (cab && !document.querySelector(".marca-novedades")) {
      cab.insertAdjacentHTML("beforebegin",
        '<div class="marca-novedades"><div class="marca-nov-titulo">\uD83C\uDF89 Novedades</div><ul>' +
        '<li><b>Más cuota por equipo:</b> ahora 6 contenedores y 1 GB de memoria (antes 4 y 512 MB).</li>' +
        '<li><b>Más espacio:</b> el servidor ahora tiene 200 GB de disco.</li>' +
        '</ul></div>');
    }
    var ayuda = h1 && h1.parentElement && h1.parentElement.querySelector("p");
    texto(ayuda, "Ingresa con tu correo institucional @utb.edu.co y tu contraseña");
    var correo = form.querySelector('input[name="email"]');
    if (correo) correo.placeholder = "usuario@utb.edu.co";
    var clave = form.querySelector('input[name="password"]');
    if (clave) clave.placeholder = "Tu contraseña";
    var boton = form.querySelector('button[type="submit"]');
    if (boton && boton.firstChild && boton.firstChild.nodeType === 3) texto(boton.firstChild, "Ingresar");

    // «Lost your password?» apuntaba a la documentación de Dokploy
    var perdida = document.querySelector('a[href*="docs.dokploy.com"]');
    if (perdida) {
      perdida.removeAttribute("href");
      perdida.removeAttribute("target");
      perdida.style.cursor = "default";
      texto(perdida, "¿Olvidaste tu contraseña? Pídesela a tu docente.");
    }
    var passkey = Array.prototype.find.call(document.querySelectorAll("button"),
      function (b) { return /passkey/i.test(b.textContent); });
    if (passkey) passkey.style.display = "none";
  }

  function aplicar() { titulo(); login(); }
  aplicar();
  new MutationObserver(aplicar).observe(document.documentElement,
    { childList: true, subtree: true, characterData: true });
})();
