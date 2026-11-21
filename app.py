import streamlit as st
import re
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="BVMT Behavioral Terminal", layout="wide", page_icon="📊")

# Style sombre façon Bloomberg
st.markdown("""
<style>
    .stApp { background-color: #000000; color: #e6edf3; }
    .ticker-bar { background-color: #0d1117; padding: 10px; border: 1px solid #262d3d; color: #00e676; font-family: monospace; font-weight: bold; }
    .card { background-color: #12161f; padding: 15px; border: 1px solid #262d3d; border-radius: 5px; margin-bottom: 12px; }
</style>
""", unsafe_allow_html=True)

ACTIONS_BVMT = [
    "BIAT", "ATTIJARI", "STB", "BNA", "BH BANK", "AMEN BANK", "BT", "UBCI", "UIB", "WIFAK",
    "SFBT", "POULINA", "PGH", "DELICE", "ONE TECH", "EURO-CYCLES", "SAH", "LILAS", "TPR",
    "SOTUVER", "ARTES", "ENNAKL", "CITY CARS", "CARTHAGE CEMENT", "SOTRAPIL", "TUNISAIR",
    "MONOPRIX", "MAGASIN GENERAL", "STAR", "ASTREE", "MAGHREBIA", "TUNIS RE", "SPDIT",
    "ATL", "TUNISIE LEASING", "CIL", "HANNIBAL LEASE", "MPBS", "LAND'OR", "UNIMED", "CELLCOM",
    "TELNET", "HEXABYTE", "ASSAD", "SIAME", "SOTEMAIL", "SOMOCER", "ICF", "ALKIMIA"
]

MOTS_DIVIDENDE = ["dividende", "assemblée générale", "distribution", "coupon", "rendement"]
MOTS_RECORD = ["record", "historique", "jamais atteint", "sommet", "explosion", "spectaculaire", "bond"]
MOTS_CHUTE = ["chute", "effondrement", "perte nette", "déficit", "suspendu", "alerte", "crise"]
MOTS_RECUL_MODERE = ["recul", "baisse", "repli", "diminution", "ralentissement", "retard"]
MOTS_HAUSSE_MODERE = ["hausse", "progression", "croissance", "amélioration", "augmentation", "rebond", "bénéfice", "excédent"]
MOTS_PROJET = ["partenariat", "nouveau", "lancement", "projet", "extension", "investissement", "accord", "stratégique"]
MOTS_REGULATION = ["cmf", "bct", "taux", "loi", "impôt", "fiscal", "réglementation", "circulaire", "banque centrale"]

@st.cache_data(ttl=600)
def charger_donnees_bvmt():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    cache_cours = {}
    tickers = []

    try:
        resp = requests.get("https://www.ilboursa.com/marches/aaz", headers=headers, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for ligne in soup.find_all("tr"):
                texte_ligne = ligne.get_text(" | ", strip=True).upper()
                cols = [td.get_text(strip=True) for td in ligne.find_all("td")]
                if not cols:
                    continue
                for action in ACTIONS_BVMT:
                    if action in texte_ligne and action not in cache_cours:
                        prix, var_str, var_num = "", "0.00%", 0.0
                        for c in cols:
                            if "%" in c and var_str == "0.00%":
                                var_str = c
                                try:
                                    var_num = float(c.replace("%", "").replace(",", ".").replace("+", "").strip())
                                except ValueError:
                                    pass
                            elif re.match(r"^\d+[.,]\d+$", c) and not prix:
                                prix = c
                        if prix:
                            cache_cours[action] = (f"{prix} DT", var_str, var_num)
                            tickers.append(f"{action} {prix} ({var_str})")
    except Exception:
        pass

    articles = []
    try:
        resp = requests.get("https://www.ilboursa.com/marches/actualites_bourse_tunis", headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            titres_vus = set()
            for lien in soup.find_all("a"):
                href = lien.get("href", "")
                titre = lien.get_text(strip=True)
                if "/marches/" in href and len(titre) > 25 and titre not in titres_vus:
                    titres_vus.add(titre)
                    url_art = href if href.startswith("http") else "https://www.ilboursa.com" + href
                    action = next((a for a in ACTIONS_BVMT if a in titre.upper()), "BVMT / MACRO")
                    texte = titre.lower()
                    resume = titre

                    try:
                        r_art = requests.get(url_art, headers=headers, timeout=5)
                        if r_art.status_code == 200:
                            s_art = BeautifulSoup(r_art.text, "html.parser")
                            ps = [p.get_text(strip=True) for p in s_art.find_all("p") if len(p.get_text(strip=True)) > 60]
                            if ps:
                                resume = ps[0].split(".")[0] + "."
                                texte += " " + " ".join(ps[:4]).lower()
                                if action == "BVMT / MACRO":
                                    action = next((a for a in ACTIONS_BVMT if a in texte.upper()), "BVMT / MACRO")
                    except Exception:
                        pass

                    prix_dt, var_str, var_num = cache_cours.get(action, ("MACRO", "", 0.0))

                    if any(m in texte for m in MOTS_DIVIDENDE):
                        biais, bleu, rouge, vert = "💰 COMPTABILITÉ MENTALE", "Le cerveau voit le dividende comme un cadeau gratuit.", "Acheter trop cher avant le paiement.", "Vérifier le cash réel de l'entreprise."
                    elif any(m in texte for m in MOTS_CHUTE) and var_num > 0.4:
                        biais, bleu, rouge, vert = "👁️ BIAIS D'ANCRAGE PASSÉ", "La foule reste bloquée sur les mauvaises nouvelles d'hier.", "Vendre au plus bas alors que le prix remonte.", "Observer si le prix résiste aux mauvaises news."
                    elif any(m in texte for m in MOTS_RECORD):
                        biais, bleu, rouge, vert = "🚀 BIAIS DE RÉCENCE (FOMO)", "La foule croit que le record va durer pour toujours.", "Acheter au sommet par peur de rater le train.", "Comparer avec les 3 dernières années."
                    elif any(m in texte for m in MOTS_CHUTE):
                        biais, bleu, rouge, vert = "😨 AVERSION À LA PERTE", "La peur de perdre pousse à fuir immédiatement.", "Vendre dans la panique sur un problème temporaire.", "Vérifier si le cœur du métier reste solide."
                    elif any(m in texte for m in MOTS_PROJET):
                        biais, bleu, rouge, vert = "✨ BIAIS NARRATIF", "Le cerveau préfère une belle histoire aux chiffres froids.", "Payer aujourd'hui pour des promesses futures.", "Attendre les prochains bilans chiffrés."
                    else:
                        biais, bleu, rouge, vert = "⏱️ BIAIS D'ACTION", "Besoin d'agir même quand rien ne change.", "Trader sur du bruit administratif.", "Ne rien faire et garder la tête froide."

                    articles.append({
                        "action": action, "prix": f"{prix_dt} ({var_str})" if var_str else prix_dt,
                        "titre": titre, "resume": resume, "lien": url_art,
                        "biais": biais, "bleu": bleu, "rouge": rouge, "vert": vert
                    })
                    if len(articles) == 12:
                        break
    except Exception:
        pass

    return tickers, articles

# --- AFFICHAGE WEB ---
st.markdown("### 🟠 `BVMT <GO>` — TUNIS STOCK EXCHANGE BEHAVIORAL TERMINAL")

if st.button("↻ Actualiser les données en direct"):
    st.cache_data.clear()

tickers, articles = charger_donnees_bvmt()

if tickers:
    st.markdown(f"<div class='ticker-bar'>{'  |  '.join(tickers[:12])}</div>", unsafe_allow_html=True)

st.write("")
filtre = st.text_input("🔍 Filtrer par action ou mot-clé (ex: BIAT, SFBT, Dividende) :", "")

for art in articles:
    if filtre.upper() in art["action"] or filtre.upper() in art["titre"].upper():
        with st.container():
            st.markdown(f"""
            <div class='card'>
                <span style='color:#ff9900; font-weight:bold; font-family:monospace;'>{art['action']}</span> &nbsp;|&nbsp;
                <span style='color:#00e676; font-family:monospace;'>{art['prix']}</span> &nbsp;|&nbsp;
                <span style='background:#1c2433; color:#00d2ff; padding:3px 8px; border-radius:4px; font-size:0.85em;'>{art['biais']}</span>
                <h4 style='color:#ffffff; margin-top:8px;'>{art['titre']}</h4>
                <p style='color:#94a3b8; font-size:0.95em;'>{art['resume']}</p>
                <p style='color:#00d2ff; margin:2px 0;'><b>🔵 Ce que la foule pense :</b> {art['bleu']}</p>
                <p style='color:#ff3b30; margin:2px 0;'><b>🔴 L'erreur qu'elle va faire :</b> {art['rouge']}</p>
                <p style='color:#00e676; margin:2px 0;'><b>🟢 Ce que tu dois faire :</b> {art['vert']}</p>
                <a href='{art['lien']}' target='_blank' style='color:#00d2ff; text-decoration:none; font-size:0.9em;'>Lire l'article source →</a>
            </div>
            """, unsafe_allow_html=True)