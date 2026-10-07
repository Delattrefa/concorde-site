/*
 * Galerie interactive — La Concorde asbl
 *
 * Visionneuse plein écran pour les photos et vidéos d'un album :
 *  - navigation : flèches à l'écran, flèches du clavier, glissement du doigt,
 *    bande de miniatures ;
 *  - compteur « 3 / 24 », légende, préchargement des photos voisines ;
 *  - lien partageable : l'adresse se termine par #photo-3 ou #video-1 et
 *    rouvre directement l'élément ;
 *  - vidéos (YouTube, Facebook...) chargées seulement avec l'accord du
 *    visiteur pour les contenus externes (bandeau de cookies).
 */
(function () {
    "use strict";

    var galerie = document.querySelector("[data-galerie]");
    var visionneuse = document.getElementById("visionneuse");

    // Menu « Aller à l'album » (fonctionne aussi sans visionneuse)
    document.querySelectorAll("[data-aller-album]").forEach(function (choix) {
        choix.addEventListener("change", function () {
            if (choix.value) { window.location.href = choix.value; }
        });
    });

    if (!galerie || !visionneuse) { return; }

    var elements = Array.prototype.slice.call(galerie.querySelectorAll(".galerie-element"));
    if (!elements.length) { return; }

    var scene = visionneuse.querySelector(".visionneuse__scene");
    var compteur = visionneuse.querySelector(".visionneuse__compteur");
    var legende = visionneuse.querySelector(".visionneuse__legende");
    var bandeMiniatures = visionneuse.querySelector(".visionneuse__miniatures");
    var courant = -1;
    var declencheur = null;

    /* ---------- Consentement aux contenus externes ---------- */
    function videosAutorisees() {
        var api = window.ConcordeConsentement;
        return !api || api.externesAcceptes();   // sans bandeau : autorisé
    }

    /* ---------- Bande de miniatures ---------- */
    elements.forEach(function (el, i) {
        var bouton = document.createElement("button");
        bouton.type = "button";
        bouton.className = "visionneuse__miniature" + (el.dataset.type === "video" ? " visionneuse__miniature--video" : "");
        bouton.setAttribute("role", "listitem");
        bouton.setAttribute("aria-label", (el.dataset.type === "video" ? "Vidéo " : "Photo ") + (i + 1));
        if (el.dataset.miniature) {
            var img = document.createElement("img");
            img.src = el.dataset.miniature;
            img.alt = "";
            img.loading = "lazy";
            bouton.appendChild(img);
        } else {
            bouton.textContent = "▶";
        }
        bouton.addEventListener("click", function () { afficher(i); });
        bandeMiniatures.appendChild(bouton);
    });
    var miniatures = bandeMiniatures.children;

    /* ---------- Affichage d'un élément ---------- */
    function viderScene() {
        while (scene.firstChild) { scene.removeChild(scene.firstChild); }
    }

    function afficherPhoto(el) {
        var img = document.createElement("img");
        img.className = "visionneuse__photo";
        img.alt = el.dataset.legende || "";
        img.decoding = "async";
        if (el.dataset.largeur && el.dataset.hauteur) {
            img.width = el.dataset.largeur;
            img.height = el.dataset.hauteur;
        }
        scene.classList.add("est-en-chargement");
        img.addEventListener("load", function () { scene.classList.remove("est-en-chargement"); });
        img.addEventListener("error", function () { scene.classList.remove("est-en-chargement"); });
        img.src = el.dataset.grande;
        scene.appendChild(img);
    }

    function afficherVideo(el) {
        var cadre = document.createElement("div");
        cadre.className = "visionneuse__video visionneuse__video--" + (el.dataset.format || "paysage");

        if (videosAutorisees()) {
            var iframe = document.createElement("iframe");
            iframe.src = el.dataset.embed;
            iframe.title = el.dataset.legende || ("Vidéo " + el.dataset.plateforme);
            iframe.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen";
            iframe.allowFullscreen = true;
            iframe.referrerPolicy = "strict-origin-when-cross-origin";
            cadre.appendChild(iframe);
        } else {
            var message = document.createElement("div");
            message.className = "visionneuse__consentement";
            var texte = document.createElement("p");
            texte.textContent = "Cette vidéo est hébergée par " + el.dataset.plateforme +
                ", qui peut déposer des cookies. Elle ne s'affiche qu'avec votre accord.";
            var accepter = document.createElement("button");
            accepter.type = "button";
            accepter.className = "btn btn--primary";
            accepter.textContent = "Afficher les vidéos";
            accepter.addEventListener("click", function () {
                window.ConcordeConsentement.accepterExternes();
            });
            var lien = document.createElement("a");
            lien.href = el.dataset.lien;
            lien.target = "_blank";
            lien.rel = "noopener";
            lien.textContent = "ou regarder sur " + el.dataset.plateforme + " ↗";
            message.appendChild(texte);
            message.appendChild(accepter);
            message.appendChild(lien);
            cadre.appendChild(message);
        }
        scene.appendChild(cadre);
    }

    function precharger(i) {
        var el = elements[(i + elements.length) % elements.length];
        if (el && el.dataset.type === "photo") { (new Image()).src = el.dataset.grande; }
    }

    function afficher(i) {
        courant = (i + elements.length) % elements.length;
        var el = elements[courant];

        viderScene();
        scene.classList.remove("est-en-chargement");
        if (el.dataset.type === "video") { afficherVideo(el); } else { afficherPhoto(el); }

        compteur.textContent = (courant + 1) + " / " + elements.length;
        var texteLegende = el.dataset.legende || "";
        if (el.dataset.type === "video") {
            texteLegende = (texteLegende ? texteLegende + " — " : "") + el.dataset.plateforme;
        }
        legende.textContent = texteLegende;
        legende.hidden = !texteLegende;

        for (var m = 0; m < miniatures.length; m++) {
            miniatures[m].classList.toggle("est-active", m === courant);
            miniatures[m].setAttribute("aria-current", m === courant ? "true" : "false");
        }
        if (miniatures[courant] && miniatures[courant].scrollIntoView) {
            miniatures[courant].scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
        }

        if (history.replaceState && el.dataset.ancre) {
            history.replaceState(null, "", "#" + el.dataset.ancre);
        }
        precharger(courant + 1);
        precharger(courant - 1);
    }

    /* ---------- Ouverture / fermeture ---------- */
    function ouvrir(i, origine) {
        declencheur = origine || null;
        visionneuse.hidden = false;
        document.documentElement.classList.add("visionneuse-ouverte");
        afficher(i);
        visionneuse.querySelector(".visionneuse__fermer").focus({ preventScroll: true });
    }

    function fermer() {
        visionneuse.hidden = true;
        document.documentElement.classList.remove("visionneuse-ouverte");
        viderScene();   // arrête une vidéo en cours de lecture
        courant = -1;
        if (history.replaceState) {
            history.replaceState(null, "", window.location.pathname + window.location.search);
        }
        if (declencheur) { declencheur.focus({ preventScroll: true }); }
    }

    elements.forEach(function (el, i) {
        el.addEventListener("click", function () { ouvrir(i, el); });
    });

    visionneuse.addEventListener("click", function (e) {
        var action = e.target.closest("[data-action]");
        if (action) {
            var nom = action.getAttribute("data-action");
            if (nom === "fermer") { fermer(); }
            else if (nom === "precedent") { afficher(courant - 1); }
            else if (nom === "suivant") { afficher(courant + 1); }
            return;
        }
        // Clic dans le fond sombre autour de la photo : fermeture
        if (e.target === visionneuse || e.target.classList.contains("visionneuse__corps") || e.target === scene) {
            fermer();
        }
    });

    document.addEventListener("keydown", function (e) {
        if (visionneuse.hidden) { return; }
        if (e.key === "Escape") { e.preventDefault(); fermer(); }
        else if (e.key === "ArrowRight") { e.preventDefault(); afficher(courant + 1); }
        else if (e.key === "ArrowLeft") { e.preventDefault(); afficher(courant - 1); }
        else if (e.key === "Home") { e.preventDefault(); afficher(0); }
        else if (e.key === "End") { e.preventDefault(); afficher(elements.length - 1); }
        else if (e.key === "Tab") {
            // Garde le focus dans la visionneuse
            var focusables = visionneuse.querySelectorAll("button, a[href], iframe");
            if (!focusables.length) { return; }
            var premier = focusables[0], dernier = focusables[focusables.length - 1];
            if (e.shiftKey && document.activeElement === premier) { e.preventDefault(); dernier.focus(); }
            else if (!e.shiftKey && document.activeElement === dernier) { e.preventDefault(); premier.focus(); }
        }
    });

    /* ---------- Glissement du doigt (smartphone) ---------- */
    var depart = null;
    scene.addEventListener("touchstart", function (e) {
        if (e.touches.length === 1) { depart = { x: e.touches[0].clientX, y: e.touches[0].clientY }; }
    }, { passive: true });
    scene.addEventListener("touchend", function (e) {
        if (!depart) { return; }
        var dx = e.changedTouches[0].clientX - depart.x;
        var dy = e.changedTouches[0].clientY - depart.y;
        depart = null;
        if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {
            afficher(courant + (dx < 0 ? 1 : -1));
        } else if (dy > 90 && Math.abs(dy) > Math.abs(dx) * 1.5) {
            fermer();   // glisser vers le bas pour fermer
        }
    }, { passive: true });

    /* ---------- Accord donné pendant que la visionneuse est ouverte ---------- */
    document.addEventListener("concorde:consentement", function (e) {
        if (!visionneuse.hidden && e.detail && e.detail.externes && elements[courant].dataset.type === "video") {
            afficher(courant);
        }
    });

    /* ---------- Lien partagé : #photo-3 / #video-1 ---------- */
    if (window.location.hash) {
        var ancre = window.location.hash.slice(1);
        var index = elements.findIndex(function (el) { return el.dataset.ancre === ancre; });
        if (index >= 0) { ouvrir(index, elements[index]); }
    }
})();
