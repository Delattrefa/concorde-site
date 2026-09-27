/**
 * Effets de fondu / ouverture au défilement.
 * Chaque élément portant une classe .fade-up / .fade-in-left / .fade-in-right
 * reçoit la classe .is-visible dès qu'il entre dans le champ de vision,
 * ce qui déclenche la transition CSS correspondante (voir main.css).
 */
(function () {
    "use strict";

    var targets = document.querySelectorAll(
        ".fade-up, .fade-in-left, .fade-in-right"
    );

    if ("IntersectionObserver" in window && targets.length) {
        var observer = new IntersectionObserver(
            function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("is-visible");
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.15, rootMargin: "0px 0px -60px 0px" }
        );

        targets.forEach(function (el) {
            observer.observe(el);
        });
    } else {
        // Navigateur trop ancien : on affiche directement le contenu
        targets.forEach(function (el) {
            el.classList.add("is-visible");
        });
    }

    // Menu mobile
    var toggle = document.querySelector(".nav-toggle");
    var nav = document.querySelector(".main-nav");
    if (toggle && nav) {
        toggle.addEventListener("click", function () {
            var isOpen = nav.classList.toggle("is-open");
            toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });
    }
})();
