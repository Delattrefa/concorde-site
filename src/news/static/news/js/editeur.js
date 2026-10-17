/*
 * Éditeur d'actualités par blocs — La Concorde asbl
 *
 * L'article est une suite de blocs (texte enrichi, intertitre, image
 * positionnée, citation, encart, lien utile) qu'on ajoute, déplace et
 * retire. Les photos sont envoyées dès qu'on les choisit
 * (news_envoyer_photo) ; le bloc ne garde que l'identifiant de l'image.
 *
 * À l'envoi du formulaire, les blocs sont écrits en JSON dans le champ
 * caché « corps », converti côté serveur par news/editeur.py (qui nettoie
 * entièrement le texte enrichi).
 */
(function () {
    "use strict";

    var editeur = document.querySelector("[data-editeur]");
    if (!editeur) { return; }

    var formulaire = editeur.closest("form");
    var champCorps = editeur.querySelector("input[name='corps']");
    var conteneur = editeur.querySelector("[data-editeur-blocs]");
    var urlPhoto = editeur.getAttribute("data-url-photo");
    var jetonCsrf = formulaire.querySelector("input[name='csrfmiddlewaretoken']").value;
    var envoisEnCours = 0;

    var LIBELLES = {
        paragraph: "Texte",
        heading: "Intertitre",
        image_positionnee: "Image",
        quote: "Citation",
        callout: "Encart",
        useful_link: "Lien utile"
    };
    var POSITIONS = [
        ["pleine", "Pleine largeur"],
        ["gauche", "À gauche"],
        ["droite", "À droite"]
    ];

    // Entrée dans un texte enrichi = nouveau paragraphe <p> (et non <div>)
    try { document.execCommand("defaultParagraphSeparator", false, "p"); } catch (e) { /* ancien navigateur */ }

    /* ---------- Petits outils DOM ---------- */
    function el(balise, attributs, enfants) {
        var noeud = document.createElement(balise);
        Object.keys(attributs || {}).forEach(function (nom) {
            if (nom === "texte") { noeud.textContent = attributs[nom]; }
            else { noeud.setAttribute(nom, attributs[nom]); }
        });
        (enfants || []).forEach(function (enfant) { if (enfant) { noeud.appendChild(enfant); } });
        return noeud;
    }

    var compteurId = 0;
    function champ(libelle, controle) {
        compteurId += 1;
        controle.id = "editeur-champ-" + compteurId;
        return el("div", { "class": "editeur__champ" }, [
            el("label", { "for": controle.id, texte: libelle }),
            controle
        ]);
    }

    function saisie(valeur, attributs) {
        var input = el("input", Object.assign({ type: "text", "class": "champ-texte" }, attributs || {}));
        input.value = valeur || "";
        return input;
    }

    /* ---------- Texte enrichi ---------- */
    function texteEnrichi(html, libelle) {
        var zone = el("div", {
            "class": "editeur__texte", contenteditable: "true", role: "textbox",
            "aria-multiline": "true", "aria-label": libelle
        });
        zone.innerHTML = html || "";

        // Collage : texte simple uniquement (pas les styles des autres sites)
        zone.addEventListener("paste", function (evenement) {
            evenement.preventDefault();
            var texte = (evenement.clipboardData || window.clipboardData).getData("text/plain");
            document.execCommand("insertText", false, texte);
        });

        function bouton(symbole, titre, action) {
            var b = el("button", { type: "button", "class": "editeur__outil", title: titre, "aria-label": titre });
            b.innerHTML = symbole;
            // mousedown : garder la sélection dans la zone de texte
            b.addEventListener("mousedown", function (evenement) { evenement.preventDefault(); });
            b.addEventListener("click", function () { zone.focus(); action(); });
            return b;
        }

        var barre = el("div", { "class": "editeur__barre", role: "toolbar", "aria-label": "Mise en forme" }, [
            bouton("<b>G</b>", "Gras", function () { document.execCommand("bold"); }),
            bouton("<i>I</i>", "Italique", function () { document.execCommand("italic"); }),
            bouton("• Liste", "Liste à puces", function () { document.execCommand("insertUnorderedList"); }),
            bouton("1. Liste", "Liste numérotée", function () { document.execCommand("insertOrderedList"); }),
            bouton("🔗 Lien", "Ajouter un lien sur le texte sélectionné", function () {
                if (window.getSelection().isCollapsed) {
                    window.alert("Sélectionnez d'abord le texte à transformer en lien.");
                    return;
                }
                var adresse = window.prompt("Adresse du lien (https://…) :", "https://");
                if (adresse && adresse !== "https://") { document.execCommand("createLink", false, adresse.trim()); }
            }),
            bouton("Retirer le lien", "Retirer le lien", function () { document.execCommand("unlink"); })
        ]);

        return {
            noeud: el("div", { "class": "editeur__enrichi" }, [barre, zone]),
            zone: zone,
            valeur: function () { return zone.innerHTML; }
        };
    }

    /* ---------- Contenu de chaque type de bloc ---------- */
    var TYPES = {
        paragraph: function (valeur) {
            var texte = texteEnrichi(valeur, "Texte");
            return { noeud: texte.noeud, focus: texte.zone, lire: texte.valeur };
        },

        heading: function (valeur) {
            var input = saisie(valeur, { "aria-label": "Intertitre", placeholder: "Intertitre", maxlength: "255" });
            return { noeud: input, focus: input, lire: function () { return input.value; } };
        },

        quote: function (valeur) {
            valeur = valeur || {};
            var texte = el("textarea", { "class": "champ-texte", rows: "3" });
            texte.value = valeur.text || "";
            var auteur = saisie(valeur.attribution, { maxlength: "255" });
            return {
                noeud: el("div", {}, [champ("Citation", texte), champ("Auteur ou source (facultatif)", auteur)]),
                focus: texte,
                lire: function () { return { text: texte.value, attribution: auteur.value }; }
            };
        },

        callout: function (valeur) {
            valeur = valeur || {};
            var titre = saisie(valeur.title, { maxlength: "255" });
            var texte = texteEnrichi(valeur.text, "Texte de l'encart");
            return {
                noeud: el("div", {}, [champ("Titre de l'encart (facultatif)", titre),
                                      el("div", { "class": "editeur__champ" }, [texte.noeud])]),
                focus: titre,
                lire: function () { return { title: titre.value, text: texte.valeur() }; }
            };
        },

        useful_link: function (valeur) {
            valeur = valeur || {};
            var titre = saisie(valeur.title, { maxlength: "255", placeholder: "Ex : Programme complet" });
            var url = saisie(valeur.url, { type: "url", placeholder: "https://…" });
            return {
                noeud: el("div", { "class": "editeur__ligne" }, [champ("Texte du lien", titre), champ("Adresse", url)]),
                focus: titre,
                lire: function () { return { title: titre.value, url: url.value }; }
            };
        },

        image_positionnee: function (valeur, apercu) {
            valeur = valeur || {};
            var etat = { image: valeur.image || null, apercu: apercu || null };
            var nomGroupe = "position-" + (compteurId += 1);

            var vignette = el("div", { "class": "editeur__vignette" });
            var fichier = el("input", { type: "file", accept: "image/jpeg,image/png,image/webp,image/gif", "class": "editeur__fichier" });
            var choisir = el("button", { type: "button", "class": "btn btn--secondary editeur__choisir" });
            var statut = el("p", { "class": "editeur__statut", "aria-live": "polite" });

            function afficher() {
                vignette.innerHTML = "";
                if (etat.apercu) {
                    vignette.appendChild(el("img", { src: etat.apercu, alt: "" }));
                } else {
                    vignette.appendChild(el("span", { texte: "Aucune photo" }));
                }
                choisir.textContent = etat.image ? "Remplacer la photo" : "Choisir une photo";
            }
            afficher();

            choisir.addEventListener("click", function () { fichier.click(); });
            fichier.addEventListener("change", function () {
                if (!fichier.files.length) { return; }
                var donnees = new FormData();
                donnees.append("photo", fichier.files[0]);
                statut.textContent = "Envoi de la photo…";
                statut.classList.remove("editeur__statut--erreur");
                choisir.disabled = true;
                envoisEnCours += 1;
                fetch(urlPhoto, {
                    method: "POST", body: donnees, credentials: "same-origin",
                    headers: { "X-CSRFToken": jetonCsrf, "X-Requested-With": "fetch" }
                }).then(function (reponse) {
                    return reponse.json().catch(function () { return {}; }).then(function (json) {
                        if (!reponse.ok || !json.id) { throw new Error(json.erreur || "La photo n'a pas pu être envoyée."); }
                        etat.image = json.id;
                        etat.apercu = json.apercu;
                        statut.textContent = "";
                        afficher();
                    });
                }).catch(function (erreur) {
                    statut.textContent = erreur.message || "La photo n'a pas pu être envoyée.";
                    statut.classList.add("editeur__statut--erreur");
                }).then(function () {
                    envoisEnCours -= 1;
                    choisir.disabled = false;
                    fichier.value = "";
                });
            });

            var positions = el("div", { "class": "editeur__positions", role: "radiogroup", "aria-label": "Position de l'image" },
                POSITIONS.map(function (position) {
                    var radio = el("input", { type: "radio", name: nomGroupe, value: position[0] });
                    radio.checked = (valeur.position || "pleine") === position[0];
                    return el("label", { "class": "editeur__position editeur__position--" + position[0] }, [
                        radio, el("span", { texte: position[1] })
                    ]);
                }));
            var legende = saisie(valeur.legende, { maxlength: "255" });

            return {
                noeud: el("div", { "class": "editeur__image" }, [
                    el("div", { "class": "editeur__photo" }, [vignette, choisir, fichier, statut]),
                    el("div", { "class": "editeur__reglages" }, [
                        el("p", { "class": "editeur__sous-titre", texte: "Position dans le texte" }), positions,
                        champ("Légende (facultatif)", legende)
                    ])
                ]),
                focus: choisir,
                lire: function () {
                    var coche = positions.querySelector("input:checked");
                    return { image: etat.image, position: coche ? coche.value : "pleine", legende: legende.value };
                },
                apercu: function () { return etat.apercu; }
            };
        }
    };

    /* ---------- Blocs : ajout, déplacement, suppression ---------- */
    function rafraichirBoutons() {
        var blocs = conteneur.children;
        Array.prototype.forEach.call(blocs, function (bloc, index) {
            bloc.querySelector("[data-monter]").disabled = index === 0;
            bloc.querySelector("[data-descendre]").disabled = index === blocs.length - 1;
        });
    }

    function creerBloc(type, valeur, apercu) {
        var contenu = TYPES[type](valeur, apercu);
        function outil(texte, titre, attribut) {
            var b = el("button", { type: "button", "class": "editeur__action", title: titre, "aria-label": titre, texte: texte });
            b.setAttribute(attribut, "");
            return b;
        }
        var monter = outil("↑", "Monter le bloc", "data-monter");
        var descendre = outil("↓", "Descendre le bloc", "data-descendre");
        var retirer = outil("✕", "Retirer le bloc", "data-retirer");

        var bloc = el("div", { "class": "editeur__bloc editeur__bloc--" + type }, [
            el("div", { "class": "editeur__entete" }, [
                el("span", { "class": "editeur__type", texte: LIBELLES[type] }),
                el("span", { "class": "editeur__actions" }, [monter, descendre, retirer])
            ]),
            el("div", { "class": "editeur__contenu" }, [contenu.noeud])
        ]);
        bloc.lireBloc = function () {
            var donnees = { type: type, value: contenu.lire() };
            if (contenu.apercu) { donnees.apercu = contenu.apercu(); }
            return donnees;
        };
        bloc.focusBloc = function () { if (contenu.focus) { contenu.focus.focus(); } };

        monter.addEventListener("click", function () {
            if (bloc.previousElementSibling) { conteneur.insertBefore(bloc, bloc.previousElementSibling); }
            rafraichirBoutons();
            monter.disabled ? descendre.focus() : monter.focus();
        });
        descendre.addEventListener("click", function () {
            if (bloc.nextElementSibling) { conteneur.insertBefore(bloc.nextElementSibling, bloc); }
            rafraichirBoutons();
            descendre.disabled ? monter.focus() : descendre.focus();
        });
        retirer.addEventListener("click", function () {
            if (window.confirm("Retirer ce bloc « " + LIBELLES[type] + " » de l'article ?")) {
                bloc.remove();
                rafraichirBoutons();
            }
        });
        return bloc;
    }

    editeur.querySelectorAll("[data-ajouter]").forEach(function (bouton) {
        bouton.addEventListener("click", function () {
            var bloc = creerBloc(bouton.getAttribute("data-ajouter"));
            conteneur.appendChild(bloc);
            rafraichirBoutons();
            bloc.focusBloc();
        });
    });

    /* ---------- Chargement et envoi ---------- */
    var initiaux = [];
    try { initiaux = JSON.parse(champCorps.value || "[]"); } catch (e) { initiaux = []; }
    initiaux.forEach(function (donnees) {
        if (TYPES[donnees.type]) { conteneur.appendChild(creerBloc(donnees.type, donnees.value, donnees.apercu)); }
    });
    rafraichirBoutons();

    formulaire.addEventListener("submit", function (evenement) {
        if (envoisEnCours > 0) {
            evenement.preventDefault();
            window.alert("Une photo est encore en cours d'envoi : patientez quelques secondes puis réessayez.");
            return;
        }
        champCorps.value = JSON.stringify(Array.prototype.map.call(conteneur.children, function (bloc) {
            return bloc.lireBloc();
        }));
    });
}());
