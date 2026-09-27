/**
 * Lightbox simple pour la galerie photos (page album).
 * Ouvre l'image en grand avec un fondu, navigation au clavier (Échap pour fermer).
 */
(function () {
    "use strict";

    var gallery = document.getElementById("lightbox-gallery");
    var lightbox = document.getElementById("lightbox");
    if (!gallery || !lightbox) return;

    var img = lightbox.querySelector(".lightbox__image");
    var caption = lightbox.querySelector(".lightbox__caption");
    var closeBtn = lightbox.querySelector(".lightbox__close");

    function openLightbox(full, captionText) {
        img.src = full;
        img.alt = captionText || "";
        caption.textContent = captionText || "";
        lightbox.classList.add("is-open");
        lightbox.setAttribute("aria-hidden", "false");
        document.body.style.overflow = "hidden";
    }

    function closeLightbox() {
        lightbox.classList.remove("is-open");
        lightbox.setAttribute("aria-hidden", "true");
        document.body.style.overflow = "";
        // Laisse le temps au fondu de sortie avant de vider la source
        setTimeout(function () {
            if (!lightbox.classList.contains("is-open")) {
                img.src = "";
            }
        }, 400);
    }

    gallery.addEventListener("click", function (event) {
        var item = event.target.closest(".photo-gallery__item");
        if (!item) return;
        openLightbox(item.getAttribute("data-full"), item.getAttribute("data-caption"));
    });

    closeBtn.addEventListener("click", closeLightbox);

    lightbox.addEventListener("click", function (event) {
        if (event.target === lightbox) closeLightbox();
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && lightbox.classList.contains("is-open")) {
            closeLightbox();
        }
    });
})();
