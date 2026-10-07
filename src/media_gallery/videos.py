"""
Reconnaissance des liens de vidéos hébergées sur d'autres sites.

À partir de l'adresse copiée depuis le navigateur (ou le bouton « Partager »
de la plateforme), on déduit l'adresse du lecteur intégrable. Aucun appel
réseau ni clé d'API n'est nécessaire. YouTube est intégré en mode « sans
cookie » (youtube-nocookie.com).

Plateformes reconnues : YouTube, Vimeo, Facebook, Dailymotion, Instagram,
TikTok.
"""
import re
from urllib.parse import parse_qs, quote, urlparse

PLATEFORMES = ["YouTube", "Vimeo", "Facebook", "Dailymotion", "Instagram", "TikTok"]


def _hote(url):
    hote = (urlparse(url).hostname or "").lower()
    return hote[4:] if hote.startswith("www.") else hote


def analyser_video(url):
    """Renvoie un dictionnaire {plateforme, identifiant, embed, lien, format}
    pour une adresse de vidéo reconnue, sinon None.
    format : « paysage » (16:9) ou « portrait » (9:16, Reels, Shorts, TikTok)."""
    url = (url or "").strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    hote = _hote(url)
    chemin = urlparse(url).path
    requete = parse_qs(urlparse(url).query)

    # --- YouTube ------------------------------------------------------------
    if hote in ("youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com") or hote == "youtu.be":
        identifiant = None
        portrait = False
        if hote == "youtu.be":
            identifiant = chemin.strip("/").split("/")[0]
        elif "v" in requete:
            identifiant = requete["v"][0]
        else:
            m = re.match(r"^/(embed|shorts|live|v)/([\w-]{6,})", chemin)
            if m:
                identifiant = m.group(2)
                portrait = m.group(1) == "shorts"
        if identifiant and re.fullmatch(r"[\w-]{6,20}", identifiant):
            return {
                "plateforme": "YouTube",
                "identifiant": identifiant,
                "embed": f"https://www.youtube-nocookie.com/embed/{identifiant}?rel=0&modestbranding=1",
                "lien": f"https://www.youtube.com/watch?v={identifiant}",
                "format": "portrait" if portrait else "paysage",
            }
        return None

    # --- Vimeo --------------------------------------------------------------
    if hote in ("vimeo.com", "player.vimeo.com"):
        m = re.search(r"/(?:video/)?(\d{5,})(?:/([0-9a-f]{6,}))?", chemin)
        if m:
            identifiant, cle = m.group(1), m.group(2) or (requete.get("h") or [None])[0]
            embed = f"https://player.vimeo.com/video/{identifiant}" + (f"?h={cle}" if cle else "")
            return {
                "plateforme": "Vimeo", "identifiant": identifiant, "embed": embed,
                "lien": f"https://vimeo.com/{identifiant}", "format": "paysage",
            }
        return None

    # --- Facebook -----------------------------------------------------------
    if hote in ("facebook.com", "m.facebook.com", "web.facebook.com", "fb.watch"):
        if hote == "fb.watch" or "/videos/" in chemin or "/watch" in chemin or "/reel/" in chemin or "/share/v/" in chemin or "/share/r/" in chemin:
            lien = url.replace("://m.facebook.com", "://www.facebook.com").replace("://web.facebook.com", "://www.facebook.com")
            portrait = "/reel/" in chemin or "/share/r/" in chemin
            return {
                "plateforme": "Facebook", "identifiant": lien,
                "embed": "https://www.facebook.com/plugins/video.php?show_text=false&href=" + quote(lien, safe=""),
                "lien": lien, "format": "portrait" if portrait else "paysage",
            }
        return None

    # --- Dailymotion --------------------------------------------------------
    if hote in ("dailymotion.com", "dai.ly"):
        m = re.search(r"/(?:video/|embed/video/)?([a-z0-9]{5,})", chemin, re.IGNORECASE)
        if m and (hote == "dai.ly" or "/video/" in chemin):
            identifiant = m.group(1)
            return {
                "plateforme": "Dailymotion", "identifiant": identifiant,
                "embed": f"https://www.dailymotion.com/embed/video/{identifiant}",
                "lien": f"https://www.dailymotion.com/video/{identifiant}", "format": "paysage",
            }
        return None

    # --- Instagram ----------------------------------------------------------
    if hote == "instagram.com":
        m = re.match(r"^/(?:[\w.]+/)?(p|reel|reels|tv)/([\w-]+)", chemin)
        if m:
            sorte = "reel" if m.group(1) in ("reel", "reels") else m.group(1)
            identifiant = m.group(2)
            return {
                "plateforme": "Instagram", "identifiant": identifiant,
                "embed": f"https://www.instagram.com/{sorte}/{identifiant}/embed",
                "lien": f"https://www.instagram.com/{sorte}/{identifiant}/", "format": "portrait",
            }
        return None

    # --- TikTok -------------------------------------------------------------
    if hote in ("tiktok.com", "m.tiktok.com"):
        m = re.search(r"/video/(\d{8,})", chemin)
        if m:
            identifiant = m.group(1)
            return {
                "plateforme": "TikTok", "identifiant": identifiant,
                "embed": f"https://www.tiktok.com/embed/v2/{identifiant}",
                "lien": url, "format": "portrait",
            }
        return None

    return None
