import tkinter as tk
import webbrowser
import threading
import time
import re
import requests
from bs4 import BeautifulSoup

ACTIONS_BVMT = [
    "BIAT", "ATTIJARI", "STB", "BNA", "BH BANK", "AMEN BANK", "BT", "UBCI", "UIB", "WIFAK",
    "SFBT", "POULINA", "PGH", "DELICE", "ONE TECH", "EURO-CYCLES", "SAH", "LILAS", "TPR",
    "SOTUVER", "ARTES", "ENNAKL", "CITY CARS", "CARTHAGE CEMENT", "SOTRAPIL", "TUNISAIR",
    "MONOPRIX", "MAGASIN GENERAL", "STAR", "ASTREE", "MAGHREBIA", "TUNIS RE", "SPDIT",
    "ATL", "TUNISIE LEASING", "CIL", "HANNIBAL LEASE", "MPBS", "LAND'OR", "UNIMED", "CELLCOM",
    "TELNET", "HEXABYTE", "ASSAD", "SIAME", "SOTEMAIL", "SOMOCER", "ICF", "ALKIMIA"
]

# --- DICTIONNAIRES DÉCLENCHEURS DE BIAIS ---
MOTS_DIVIDENDE = ["dividende", "assemblée générale", "distribution", "coupon", "rendement"]
MOTS_RECORD = ["record", "historique", "jamais atteint", "sommet", "explosion", "spectaculaire", "bond"]
MOTS_CHUTE = ["chute", "effondrement", "perte nette", "déficit", "suspendu", "alerte", "crise"]
MOTS_RECUL_MODERE = ["recul", "baisse", "repli", "diminution", "ralentissement", "retard"]
MOTS_HAUSSE_MODERE = ["hausse", "progression", "croissance", "amélioration", "augmentation", "rebond", "bénéfice", "excédent"]
MOTS_PROJET = ["partenariat", "nouveau", "lancement", "projet", "extension", "investissement", "accord", "stratégique"]
MOTS_REGULATION = ["cmf", "bct", "taux", "loi", "impôt", "fiscal", "réglementation", "circulaire", "banque centrale"]

# --- LEXIQUE PÉDAGOGIQUE DES BIAIS ---
LEXIQUE_BIAIS = {
    "COMPTABILITÉ MENTALE": "Le cerveau range l'argent dans des 'cases' séparées. En bourse, les investisseurs traitent le dividende comme un cadeau gratuit, oubliant que le cours de l'action baisse mécaniquement du même montant lors du détachement.",
    "EFFET DE DISPOSITION": "Tendance irrationnelle à vendre trop vite les actions qui gagnent (pour sécuriser un petit profit par peur qu'il disparaisse) et à garder trop longtemps celles qui perdent (en espérant revenir à zéro).",
    "BIAIS D'ANCRAGE PASSÉ": "Le cerveau reste bloqué sur un ancien chiffre ou un mauvais souvenir. Même quand le prix commence à remonter, la foule reste paralysée par les mauvaises nouvelles d'hier.",
    "BIAIS DE RÉCENCE": "Croire que la performance récente va durer pour toujours. Après une annonce record, la foule extrapole une croissance infinie et achète souvent au sommet par peur de rater le train (FOMO).",
    "AVERSION À LA PERTE": "La douleur psychologique d'une perte est deux fois plus intense que le plaisir d'un gain équivalent. Face à des mots alarmants, l'investisseur vend dans la panique pour stopper l'inconfort.",
    "BIAIS DE DISPONIBILITÉ": "Évaluer un risque uniquement selon les infos les plus spectaculaires ou récentes dans les médias (BCT, CMF, fiscalité), en oubliant la réalité opérationnelle propre à chaque société.",
    "BIAIS NARRATIF": "L'être humain préfère une belle histoire (nouveau partenariat, lancement, expansion) aux chiffres froids. Le marché achète la promesse future avant même qu'elle ne génère du cash.",
    "BIAIS D'ANCRAGE": "Se fixer sur un seul chiffre de référence (ex: le trimestre dernier) au lieu d'évaluer la trajectoire globale et la rentabilité de l'entreprise sur plusieurs années.",
    "BIAIS D'ACTION": "L'inactivité donne l'impression de perdre le contrôle. Le cerveau pousse à acheter ou vendre sur des nouvelles administratives neutres juste pour avoir le sentiment d'agir."
}

# --- PALETTE BLOOMBERG TERMINAL ---
BB_BLACK = "#000000"
BB_PANEL = "#0b0e14"
BB_CARD = "#12161f"
BB_BORDER = "#262d3d"
BB_AMBER = "#ff9900"
BB_AMBER_DIM = "#b36b00"
BB_CYAN = "#00d2ff"
BB_GREEN = "#00e676"
BB_RED = "#ff3b30"
BB_TEXT = "#e6edf3"
BB_MUTED = "#7d8590"
BB_SELECT = "#1c2433"

cache_cours = {}
donnees_articles = []
filtre_categorie_actif = "ALL"

def charger_table_cotations(headers):
    """Télécharge tout le tableau A-Z des cotations BVMT en une seule requête."""
    cache_cours.clear()
    ticker_list = []
    try:
        resp = requests.get("https://www.ilboursa.com/marches/aaz", headers=headers, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for ligne in soup.find_all("tr"):
                texte_ligne = ligne.get_text(" | ", strip=True).upper()
                colonnes = [td.get_text(strip=True) for td in ligne.find_all("td")]
                if not colonnes:
                    continue
                for action in ACTIONS_BVMT:
                    if action in texte_ligne and action not in cache_cours:
                        prix = ""
                        var_str = "0.00%"
                        var_num = 0.0
                        for col in colonnes:
                            if "%" in col and var_str == "0.00%":
                                var_str = col
                                try:
                                    var_num = float(col.replace("%", "").replace(",", ".").replace("+", "").strip())
                                except ValueError:
                                    var_num = 0.0
                            elif re.match(r"^\d+[.,]\d+$", col) and not prix:
                                prix = col
                        if prix:
                            cache_cours[action] = (f"{prix} DT", var_str, var_num)
                            ticker_list.append((action, prix, var_str, var_num))
    except Exception:
        pass
    return ticker_list

def diagnostiquer_biais(url_article, titre, headers):
    action_trouvee = "BVMT / MACRO"
    for action in ACTIONS_BVMT:
        if action in titre.upper():
            action_trouvee = action
            break

    resume = titre
    texte_complet = titre.lower()

    try:
        resp = requests.get(url_article, headers=headers, timeout=6)
        if resp.status_code == 200:
            soup_art = BeautifulSoup(resp.text, "html.parser")
            paragraphes = soup_art.find_all("p")
            textes_valides = [p.get_text(strip=True) for p in paragraphes if len(p.get_text(strip=True)) > 60]
            if textes_valides:
                premiere_phrase = textes_valides[0].split(".")[0] + "."
                resume = premiere_phrase if len(premiere_phrase) <= 220 else premiere_phrase[:217] + "..."
                texte_complet += " " + " ".join(textes_valides[:4]).lower()

                if action_trouvee == "BVMT / MACRO":
                    for action in ACTIONS_BVMT:
                        if action in texte_complet.upper():
                            action_trouvee = action
                            break
    except Exception:
        pass

    prix_dt, var_str, var_prix = cache_cours.get(action_trouvee, ("N/A", "0.00%", 0.0))

    c_div = sum(1 for m in MOTS_DIVIDENDE if m in texte_complet)
    c_rec = sum(1 for m in MOTS_RECORD if m in texte_complet)
    c_chute = sum(1 for m in MOTS_CHUTE if m in texte_complet)
    c_recul = sum(1 for m in MOTS_RECUL_MODERE if m in texte_complet)
    c_hausse = sum(1 for m in MOTS_HAUSSE_MODERE if m in texte_complet)
    c_projet = sum(1 for m in MOTS_PROJET if m in texte_complet)
    c_reg = sum(1 for m in MOTS_REGULATION if m in texte_complet)

    if c_div > 0:
        return {
            "action": action_trouvee, "prix": prix_dt, "var_str": var_str, "var_num": var_prix,
            "titre": titre, "resume": resume, "lien": url_article,
            "cle": "COMPTABILITÉ MENTALE", "categorie": "TRAP",
            "badge": "COMPTABILITÉ MENTALE", "couleur": "#c084fc",
            "mecanisme": "Le cerveau sépare le dividende du capital comme un 'bonus gratuit', ignorant l'ajustement mécanique du cours à la baisse le jour du détachement.",
            "erreur": "Surpayer le titre à l'approche de l'AGO uniquement pour encaisser le coupon.",
            "posture": "Vérifier le Free Cash-Flow et le taux de distribution réel plutôt que le rendement facial."
        }
    elif (c_hausse + c_rec) > (c_chute + c_recul) and var_prix < -0.4:
        return {
            "action": action_trouvee, "prix": prix_dt, "var_str": var_str, "var_num": var_prix,
            "titre": titre, "resume": resume, "lien": url_article,
            "cle": "EFFET DE DISPOSITION", "categorie": "CONTRARIAN",
            "badge": "EFFET DE DISPOSITION", "couleur": BB_AMBER,
            "mecanisme": "Aversion au regret : les acheteurs précoces verrouillent leurs gains dès l'officialisation de la bonne nouvelle ('Sell the News').",
            "erreur": "Interpréter ce repli technique comme une détérioration fondamentale de la société.",
            "posture": "Analyser les volumes vendeurs : si la baisse se fait sans volume, la tendance de fond reste intacte."
        }
    elif (c_chute + c_recul) > c_hausse and var_prix > 0.4:
        return {
            "action": action_trouvee, "prix": prix_dt, "var_str": var_str, "var_num": var_prix,
            "titre": titre, "resume": resume, "lien": url_article,
            "cle": "BIAIS D'ANCRAGE PASSÉ", "categorie": "CONTRARIAN",
            "badge": "DIVERGENCE / ANCRAGE", "couleur": BB_GREEN,
            "mecanisme": "Les particuliers restent ancrés sur les chiffres décevants du passé, alors que le marché avait déjà intégré un scénario pire.",
            "erreur": "Vendre au plus bas au moment précis où les mains fortes absorbent l'offre.",
            "posture": "Signal contrarien fort : un titre qui monte sur une mauvaise nouvelle signale une capitulation des vendeurs."
        }
    elif c_rec >= 1:
        return {
            "action": action_trouvee, "prix": prix_dt, "var_str": var_str, "var_num": var_prix,
            "titre": titre, "resume": resume, "lien": url_article,
            "cle": "BIAIS DE RÉCENCE", "categorie": "HYPE",
            "badge": "BIAIS DE RÉCENCE (FOMO)", "couleur": BB_CYAN,
            "mecanisme": "Extrapolation linéaire : le cerveau projette les performances records actuelles sur les années futures sans intégrer le retour à la moyenne.",
            "erreur": "Chasser le prix après le rallye par peur de manquer l'opportunité (Herding).",
            "posture": "Comparer la croissance actuelle à la moyenne historique sur 3 à 5 ans avant d'entrer."
        }
    elif c_chute >= 1:
        return {
            "action": action_trouvee, "prix": prix_dt, "var_str": var_str, "var_num": var_prix,
            "titre": titre, "resume": resume, "lien": url_article,
            "cle": "AVERSION À LA PERTE", "categorie": "FEAR",
            "badge": "AVERSION À LA PERTE", "couleur": BB_RED,
            "mecanisme": "Asymétrie émotionnelle : la perte pèse 2x plus lourd que le gain. Le cadrage alarmiste déclenche une liquidation réflexe.",
            "erreur": "Céder des actifs solides sur un choc comptable ou conjoncturel temporaire.",
            "posture": "Isoler l'élément exceptionnel du résultat d'exploitation récurrent (EBIT)."
        }
    elif c_reg >= 1:
        return {
            "action": action_trouvee, "prix": prix_dt, "var_str": var_str, "var_num": var_prix,
            "titre": titre, "resume": resume, "lien": url_article,
            "cle": "BIAIS DE DISPONIBILITÉ", "categorie": "TRAP",
            "badge": "BIAIS DE DISPONIBILITÉ", "couleur": "#818cf8",
            "mecanisme": "L'actualité réglementaire ou macro (BCT, CMF, fiscalité) sature l'attention et crée une perception uniforme du risque.",
            "erreur": "Pénaliser indifféremment tout un secteur sans distinguer le pouvoir de fixation des prix (Pricing Power).",
            "posture": "Identifier les bilans capables d'absorber la contrainte ou d'en tirer avantage."
        }
    elif c_projet >= 1:
        return {
            "action": action_trouvee, "prix": prix_dt, "var_str": var_str, "var_num": var_prix,
            "titre": titre, "resume": resume, "lien": url_article,
            "cle": "BIAIS NARRATIF", "categorie": "HYPE",
            "badge": "BIAIS NARRATIF", "couleur": "#2dd4bf",
            "mecanisme": "Attraction pour le storytelling : une histoire d'expansion séduit plus que les ratios bilanciels.",
            "erreur": "Valoriser immédiatement des revenus futurs incertains comme s'ils étaient déjà acquis.",
            "posture": "Exiger une validation chiffrée dans les deux prochains trimestres avant d'allouer du capital."
        }
    elif c_recul > 0 or c_hausse > 0:
        return {
            "action": action_trouvee, "prix": prix_dt, "var_str": var_str, "var_num": var_prix,
            "titre": titre, "resume": resume, "lien": url_article,
            "cle": "BIAIS D'ANCRAGE", "categorie": "TRAP",
            "badge": "ANCRAGE COURT TERME", "couleur": "#cbd5e1",
            "mecanisme": "Focalisation étroite sur la variation séquentielle (T-1) au détriment de la création de valeur globale.",
            "erreur": "Sur-interpréter un bruit statistique ou saisonnier normal.",
            "posture": "Replacer la variation dans le cycle annuel complet de l'activité."
        }
    else:
        return {
            "action": action_trouvee, "prix": prix_dt, "var_str": var_str, "var_num": var_prix,
            "titre": titre, "resume": resume, "lien": url_article,
            "cle": "BIAIS D'ACTION", "categorie": "NEUTRAL",
            "badge": "BIAIS D'ACTION (BRUIT)", "couleur": BB_MUTED,
            "mecanisme": "Besoin psychologique d'intervention : l'inaction est perçue comme une perte de contrôle.",
            "erreur": "Générer des frais de courtage sur des publications administratives sans impact financier.",
            "posture": "Discipline d'inaction : conserver sa position sans réagir au bruit."
        }

# --- FONCTIONS D'INTERFACE TERMINAL ---

def selectionner_article(item):
    """Affiche l'analyse complète d'un article dans le panneau d'inspection de droite."""
    try:
        if not fenetre.winfo_exists():
            return
        lbl_insp_ticker.config(text=f"TICKER: {item['action']}")
        
        if item["prix"] != "N/A":
            c_var = BB_GREEN if item["var_num"] > 0 else (BB_RED if item["var_num"] < 0 else BB_TEXT)
            lbl_insp_cours.config(text=f"LAST: {item['prix']}  ({item['var_str']})", fg=c_var)
        else:
            lbl_insp_cours.config(text="LAST: INDICE / MACRO", fg=BB_MUTED)

        lbl_insp_badge.config(text=f" {item['badge']} ", fg=BB_BLACK, bg=item["couleur"])
        lbl_insp_titre.config(text=item["titre"])
        lbl_insp_resume.config(text=item["resume"])

        lbl_val_meca.config(text=item["mecanisme"])
        lbl_val_err.config(text=item["erreur"])
        lbl_val_post.config(text=item["posture"])

        btn_insp_source.config(command=lambda u=item["lien"]: webbrowser.open(u))
        
        # Synchronise automatiquement le lexique en bas à droite
        var_menu_lexique.set(item["cle"])
        maj_lexique(item["cle"])
    except tk.TclError:
        pass

def maj_lexique(cle):
    try:
        if fenetre.winfo_exists():
            lbl_lex_titre.config(text=f"REFERENCE DESK // {cle}")
            lbl_lex_desc.config(text=LEXIQUE_BIAIS.get(cle, ""))
    except tk.TclError:
        pass

def rafraichir_liste_gauche():
    """Filtre et affiche les lignes du terminal à gauche selon la recherche et le bouton actif."""
    try:
        if not fenetre.winfo_exists():
            return
        for w in frame_liste_gauche.winfo_children():
            w.destroy()

        recherche = entry_recherche.get().strip().upper()
        if recherche == "FILTER TICKER / KEYWORD...":
            recherche = ""

        affiches = 0
        for idx, item in enumerate(donnees_articles):
            if filtre_categorie_actif != "ALL" and item["categorie"] != filtre_categorie_actif:
                continue
            if recherche and (recherche not in item["action"] and recherche not in item["titre"].upper()):
                continue

            row = tk.Frame(frame_liste_gauche, bg=BB_CARD, highlightbackground=BB_BORDER, highlightthickness=1, padx=10, pady=8, cursor="hand2")
            row.pack(fill=tk.X, padx=6, pady=3)

            # Ligne 1 de la cellule : Ticker + Prix + Badge Biais
            r_top = tk.Frame(row, bg=BB_CARD)
            r_top.pack(fill=tk.X)

            lbl_t = tk.Label(r_top, text=f"{item['action']:<14}", font=("Consolas", 10, "bold"), bg=BB_CARD, fg=BB_AMBER)
            lbl_t.pack(side=tk.LEFT)

            if item["prix"] != "N/A":
                c_p = BB_GREEN if item["var_num"] > 0 else (BB_RED if item["var_num"] < 0 else BB_TEXT)
                lbl_p = tk.Label(r_top, text=f"{item['prix']} ({item['var_str']})", font=("Consolas", 9, "bold"), bg=BB_CARD, fg=c_p)
                lbl_p.pack(side=tk.LEFT, padx=(6, 0))
            else:
                lbl_p = tk.Label(r_top, text="MACRO", font=("Consolas", 9), bg=BB_CARD, fg=BB_MUTED)
                lbl_p.pack(side=tk.LEFT, padx=(6, 0))

            lbl_b = tk.Label(r_top, text=item["badge"], font=("Consolas", 8, "bold"), bg=BB_CARD, fg=item["couleur"])
            lbl_b.pack(side=tk.RIGHT)

            # Ligne 2 de la cellule : Titre condensé
            lbl_headline = tk.Label(
                row, text=item["titre"], font=("Segoe UI", 9, "bold"),
                bg=BB_CARD, fg=BB_TEXT, anchor="w", justify="left", wraplength=540
            )
            lbl_headline.pack(fill=tk.X, pady=(4, 0))

            # Rendre toute la ligne cliquable + effet survol
            widgets_row = [row, r_top, lbl_t, lbl_p, lbl_b, lbl_headline]
            for w in widgets_row:
                w.bind("<Button-1>", lambda e, it=item: selectionner_article(it))
                w.bind("<Enter>", lambda e, r=row, ws=widgets_row: [x.config(bg=BB_SELECT) for x in ws])
                w.bind("<Leave>", lambda e, r=row, ws=widgets_row: [x.config(bg=BB_CARD) for x in ws])

            if affiches == 0:
                selectionner_article(item)
            affiches += 1

        lbl_count_feed.config(text=f"DISPLAYING {affiches} / {len(donnees_articles)} SIGNALS")
    except tk.TclError:
        pass

def changer_filtre(cat):
    global filtre_categorie_actif
    filtre_categorie_actif = cat
    for code, btn in boutons_filtres.items():
        if code == cat:
            btn.config(bg=BB_AMBER, fg=BB_BLACK)
        else:
            btn.config(bg=BB_CARD, fg=BB_TEXT)
    rafraichir_liste_gauche()

def maj_ticker_tape(ticker_list):
    try:
        if not fenetre.winfo_exists():
            return
        if not ticker_list:
            lbl_ticker_tape.config(text="BVMT LIVE FEED // EN ATTENTE DE COTATIONS...")
            return
        morceaux = []
        for act, prx, var_s, var_n in ticker_list[:14]:
            fleche = "▲" if var_n > 0 else ("▼" if var_n < 0 else "•")
            morceaux.append(f"{act} {prx} {fleche}{var_s}")
        lbl_ticker_tape.config(text="   |   ".join(morceaux))
    except tk.TclError:
        pass

def maj_telemetrie_globale():
    try:
        if not fenetre.winfo_exists():
            return
        nb_hype = sum(1 for x in donnees_articles if x["categorie"] == "HYPE")
        nb_fear = sum(1 for x in donnees_articles if x["categorie"] == "FEAR")
        nb_cont = sum(1 for x in donnees_articles if x["categorie"] == "CONTRARIAN")
        nb_trap = sum(1 for x in donnees_articles if x["categorie"] == "TRAP")
        
        lbl_tel_hype.config(text=f"FOMO/HYPE: {nb_hype}")
        lbl_tel_fear.config(text=f"PANIC/LOSS: {nb_fear}")
        lbl_tel_cont.config(text=f"CONTRARIAN: {nb_cont}")
        lbl_tel_trap.config(text=f"COGNITIVE TRAPS: {nb_trap}")
    except tk.TclError:
        pass

def tache_scan_terminal():
    try:
        if fenetre.winfo_exists():
            fenetre.after(0, lambda: lbl_status_sys.config(text="STATUS: SYNCING BVMT DATA...", fg=BB_AMBER))
            fenetre.after(0, lambda: btn_go.config(state=tk.DISABLED, bg=BB_AMBER_DIM))
    except tk.TclError:
        return

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    # 1. Chargement des cotations en direct
    tickers = charger_table_cotations(headers)
    fenetre.after(0, maj_ticker_tape, tickers)

    # 2. Chargement et analyse comportementale des news
    nouveaux_articles = []
    try:
        resp = requests.get("https://www.ilboursa.com/marches/actualites_bourse_tunis", headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            titres_vus = set()
            for lien in soup.find_all("a"):
                try:
                    if not fenetre.winfo_exists():
                        return
                except tk.TclError:
                    return

                href = lien.get("href", "")
                titre = lien.get_text(strip=True)
                if "/marches/" in href and len(titre) > 25 and titre not in titres_vus:
                    titres_vus.add(titre)
                    lien_complet = href if href.startswith("http") else "https://www.ilboursa.com" + href
                    item = diagnostiquer_biais(lien_complet, titre, headers)
                    nouveaux_articles.append(item)
                    if len(nouveaux_articles) == 14:
                        break

            donnees_articles.clear()
            donnees_articles.extend(nouveaux_articles)
            fenetre.after(0, rafraichir_liste_gauche)
            fenetre.after(0, maj_telemetrie_globale)
            fenetre.after(0, lambda: lbl_status_sys.config(text="STATUS: ONLINE // BVMT LIVE", fg=BB_GREEN))
        else:
            fenetre.after(0, lambda: lbl_status_sys.config(text=f"ERR HTTP {resp.status_code}", fg=BB_RED))
    except Exception as e:
        fenetre.after(0, lambda: lbl_status_sys.config(text="ERR NETWORK OFFLINE", fg=BB_RED))

    fenetre.after(0, lambda: btn_go.config(state=tk.NORMAL, bg=BB_AMBER))

def lancer_scan():
    threading.Thread(target=tache_scan_terminal, daemon=True).start()

def maj_horloge():
    try:
        if fenetre.winfo_exists():
            lbl_clock.config(text=time.strftime("TUNIS %H:%M:%S CET"))
            fenetre.after(1000, maj_horloge)
    except tk.TclError:
        pass

# ==============================================================================
# CONSTRUCTION DE L'INTERFACE BLOOMBERG WORKSTATION
# ==============================================================================
fenetre = tk.Tk()
fenetre.title("BVMT BEHAVIORAL TERMINAL // INSTITUTIONAL WORKSTATION")
fenetre.geometry("1340x860")
fenetre.configure(bg=BB_BLACK)

# --- 1. BARRE SUPÉRIEURE DE COMMANDE (BLOOMBERG HEADER) ---
top_bar = tk.Frame(fenetre, bg=BB_BLACK, highlightbackground=BB_BORDER, highlightthickness=1, padx=12, pady=6)
top_bar.pack(fill=tk.X)

tk.Label(top_bar, text="BVMT <GO>", font=("Consolas", 13, "bold"), bg=BB_AMBER, fg=BB_BLACK, padx=8, pady=2).pack(side=tk.LEFT)
tk.Label(top_bar, text=" TUNIS STOCK EXCHANGE // BEHAVIORAL & SENTIMENT TERMINAL", font=("Consolas", 11, "bold"), bg=BB_BLACK, fg=BB_AMBER).pack(side=tk.LEFT, padx=8)

lbl_clock = tk.Label(top_bar, text="", font=("Consolas", 10, "bold"), bg=BB_BLACK, fg=BB_CYAN)
lbl_clock.pack(side=tk.RIGHT, padx=(12, 0))

lbl_status_sys = tk.Label(top_bar, text="STATUS: READY", font=("Consolas", 10, "bold"), bg=BB_BLACK, fg=BB_GREEN)
lbl_status_sys.pack(side=tk.RIGHT, padx=12)

# --- 2. BANDEAU DÉFILANT DES COTATIONS (TICKER TAPE) ---
tape_frame = tk.Frame(fenetre, bg="#0d1117", highlightbackground=BB_BORDER, highlightthickness=1, padx=10, pady=4)
tape_frame.pack(fill=tk.X)
lbl_ticker_tape = tk.Label(tape_frame, text="INITIALIZING BVMT MARKET DATA STREAM...", font=("Consolas", 9, "bold"), bg="#0d1117", fg=BB_GREEN, anchor="w")
lbl_ticker_tape.pack(fill=tk.X)

# --- 3. BARRE DE TÉLÉMÉTRIE PSYCHOLOGIQUE & RECHERCHE ---
cmd_bar = tk.Frame(fenetre, bg=BB_PANEL, highlightbackground=BB_BORDER, highlightthickness=1, padx=12, pady=8)
cmd_bar.pack(fill=tk.X)

# Champ de recherche style commande
entry_recherche = tk.Entry(cmd_bar, font=("Consolas", 10, "bold"), bg=BB_BLACK, fg=BB_AMBER, insertbackground=BB_AMBER, width=28, relief=tk.FLAT, highlightbackground=BB_AMBER, highlightthickness=1)
entry_recherche.insert(0, "FILTER TICKER / KEYWORD...")
entry_recherche.pack(side=tk.LEFT, ipady=4)

def on_entry_focus_in(e):
    if entry_recherche.get() == "FILTER TICKER / KEYWORD...":
        entry_recherche.delete(0, tk.END)

def on_entry_focus_out(e):
    if not entry_recherche.get():
        entry_recherche.insert(0, "FILTER TICKER / KEYWORD...")

entry_recherche.bind("<FocusIn>", on_entry_focus_in)
entry_recherche.bind("<FocusOut>", on_entry_focus_out)
entry_recherche.bind("<KeyRelease>", lambda e: rafraichir_liste_gauche())

btn_go = tk.Button(cmd_bar, text="SCAN <GO>", font=("Consolas", 9, "bold"), bg=BB_AMBER, fg=BB_BLACK, relief=tk.FLAT, padx=10, pady=3, cursor="hand2", command=lancer_scan)
btn_go.pack(side=tk.LEFT, padx=(6, 18))

# Boutons de filtrage rapide par biais
boutons_filtres = {}
filtres_def = [("ALL", "ALL"), ("CONTRARIAN", "CONTRARIAN"), ("FEAR", "FEAR/PANIC"), ("HYPE", "FOMO/HYPE"), ("TRAP", "TRAPS")]
for code, label in filtres_def:
    bg_init = BB_AMBER if code == "ALL" else BB_CARD
    fg_init = BB_BLACK if code == "ALL" else BB_TEXT
    b = tk.Button(cmd_bar, text=label, font=("Consolas", 8, "bold"), bg=bg_init, fg=fg_init, relief=tk.FLAT, padx=8, pady=4, cursor="hand2", command=lambda c=code: changer_filtre(c))
    b.pack(side=tk.LEFT, padx=2)
    boutons_filtres[code] = b

# Compteurs télémétriques à droite
tel_box = tk.Frame(cmd_bar, bg=BB_PANEL)
tel_box.pack(side=tk.RIGHT)

lbl_tel_hype = tk.Label(tel_box, text="FOMO/HYPE: 0", font=("Consolas", 9, "bold"), bg=BB_PANEL, fg=BB_CYAN)
lbl_tel_hype.pack(side=tk.LEFT, padx=8)
lbl_tel_fear = tk.Label(tel_box, text="PANIC/LOSS: 0", font=("Consolas", 9, "bold"), bg=BB_PANEL, fg=BB_RED)
lbl_tel_fear.pack(side=tk.LEFT, padx=8)
lbl_tel_cont = tk.Label(tel_box, text="CONTRARIAN: 0", font=("Consolas", 9, "bold"), bg=BB_PANEL, fg=BB_GREEN)
lbl_tel_cont.pack(side=tk.LEFT, padx=8)
lbl_tel_trap = tk.Label(tel_box, text="COGNITIVE TRAPS: 0", font=("Consolas", 9, "bold"), bg=BB_PANEL, fg="#c084fc")
lbl_tel_trap.pack(side=tk.LEFT, padx=8)

# --- 4. ESPACE PRINCIPAL DIVISÉ (SPLIT WORKSTATION) ---
workspace = tk.Frame(fenetre, bg=BB_BLACK)
workspace.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

# === PANNEAU GAUCHE : FLUX D'ACTUALITÉS & SIGNAUX ===
left_pane = tk.Frame(workspace, bg=BB_PANEL, highlightbackground=BB_BORDER, highlightthickness=1, width=620)
left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
left_pane.pack_propagate(False)

left_header = tk.Frame(left_pane, bg="#161b26", padx=10, pady=5)
left_header.pack(fill=tk.X)
tk.Label(left_header, text="LIVE NEWS & BEHAVIORAL FEED", font=("Consolas", 9, "bold"), bg="#161b26", fg=BB_AMBER).pack(side=tk.LEFT)
lbl_count_feed = tk.Label(left_header, text="0 SIGNALS", font=("Consolas", 8), bg="#161b26", fg=BB_MUTED)
lbl_count_feed.pack(side=tk.RIGHT)

canvas_left = tk.Canvas(left_pane, bg=BB_PANEL, highlightthickness=0)
scroll_left = tk.Scrollbar(left_pane, orient="vertical", command=canvas_left.yview)
frame_liste_gauche = tk.Frame(canvas_left, bg=BB_PANEL)

frame_liste_gauche.bind("<Configure>", lambda e: canvas_left.configure(scrollregion=canvas_left.bbox("all")))
win_left = canvas_left.create_window((0, 0), window=frame_liste_gauche, anchor="nw")
canvas_left.bind("<Configure>", lambda e: canvas_left.itemconfig(win_left, width=e.width))
canvas_left.configure(yscrollcommand=scroll_left.set)

canvas_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scroll_left.pack(side=tk.RIGHT, fill=tk.Y)

def _on_mousewheel(event):
    canvas_left.yview_scroll(int(-1 * (event.delta / 120)), "units")

canvas_left.bind_all("<MouseWheel>", _on_mousewheel)

# === PANNEAU DROIT : INSPECTEUR DÉTAILLÉ + LEXIQUE ===
right_pane = tk.Frame(workspace, bg=BB_BLACK)
right_pane.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 0))

# Sous-panneau Droit Haut : Inspecteur Approfondi
inspector = tk.Frame(right_pane, bg=BB_PANEL, highlightbackground=BB_BORDER, highlightthickness=1, padx=18, pady=14)
inspector.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

insp_top = tk.Frame(inspector, bg=BB_PANEL)
insp_top.pack(fill=tk.X, pady=(0, 10))

lbl_insp_ticker = tk.Label(insp_top, text="TICKER: --", font=("Consolas", 13, "bold"), bg=BB_PANEL, fg=BB_AMBER)
lbl_insp_ticker.pack(side=tk.LEFT)

lbl_insp_cours = tk.Label(insp_top, text="LAST: --", font=("Consolas", 11, "bold"), bg=BB_PANEL, fg=BB_TEXT)
lbl_insp_cours.pack(side=tk.LEFT, padx=16)

lbl_insp_badge = tk.Label(insp_top, text=" SIGNAL ", font=("Consolas", 9, "bold"), bg=BB_AMBER, fg=BB_BLACK, padx=6, pady=2)
lbl_insp_badge.pack(side=tk.RIGHT)

lbl_insp_titre = tk.Label(inspector, text="Sélectionnez une actualité dans le flux de gauche pour inspecter l'analyse comportementale.", font=("Segoe UI", 12, "bold"), bg=BB_PANEL, fg=BB_TEXT, anchor="w", justify="left", wraplength=620)
lbl_insp_titre.pack(fill=tk.X, pady=(4, 8))

lbl_insp_resume = tk.Label(inspector, text="", font=("Segoe UI", 10), bg=BB_PANEL, fg=BB_MUTED, anchor="w", justify="left", wraplength=620)
lbl_insp_resume.pack(fill=tk.X, pady=(0, 14))

# Grille des 3 piliers comportementaux dans l'inspecteur
def creer_bloc_analyse(parent, titre_bloc, couleur_titre):
    box = tk.Frame(parent, bg=BB_CARD, highlightbackground=BB_BORDER, highlightthickness=1, padx=12, pady=8)
    box.pack(fill=tk.X, pady=4)
    tk.Label(box, text=titre_bloc, font=("Consolas", 9, "bold"), bg=BB_CARD, fg=couleur_titre, anchor="w").pack(fill=tk.X)
    lbl_val = tk.Label(box, text="--", font=("Segoe UI", 9), bg=BB_CARD, fg=BB_TEXT, anchor="w", justify="left", wraplength=590)
    lbl_val.pack(fill=tk.X, pady=(3, 0))
    return lbl_val

lbl_val_meca = creer_bloc_analyse(inspector, "1. MÉCANISME COGNITIF (CE QUI SE PASSE DANS LA TÊTE DE LA FOULE)", BB_CYAN)
lbl_val_err = creer_bloc_analyse(inspector, "2. ERREUR TYPIQUE DES INVESTISSEURS (LE PIÈGE)", BB_RED)
lbl_val_post = creer_bloc_analyse(inspector, "3. POSTURE RATIONNELLE (EXÉCUTION FROIDE)", BB_GREEN)

insp_bottom = tk.Frame(inspector, bg=BB_PANEL)
insp_bottom.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

btn_insp_source = tk.Button(insp_bottom, text="OPEN FULL ARTICLE <GO>", font=("Consolas", 9, "bold"), bg=BB_CYAN, fg=BB_BLACK, relief=tk.FLAT, padx=12, pady=5, cursor="hand2")
btn_insp_source.pack(side=tk.RIGHT)

# Sous-panneau Droit Bas : Lexique Pédagogique des Biais
lexique_box = tk.Frame(right_pane, bg="#0d1117", highlightbackground=BB_AMBER_DIM, highlightthickness=1, padx=16, pady=12)
lexique_box.pack(fill=tk.X, side=tk.BOTTOM)

lex_top = tk.Frame(lexique_box, bg="#0d1117")
lex_top.pack(fill=tk.X, pady=(0, 6))

lbl_lex_titre = tk.Label(lex_top, text="REFERENCE DESK // COGNITIVE BIAS GLOSSARY", font=("Consolas", 10, "bold"), bg="#0d1117", fg=BB_AMBER)
lbl_lex_titre.pack(side=tk.LEFT)

var_menu_lexique = tk.StringVar(value="COMPTABILITÉ MENTALE")
menu_lex = tk.OptionMenu(lex_top, var_menu_lexique, *LEXIQUE_BIAIS.keys(), command=maj_lexique)
menu_lex.config(bg=BB_CARD, fg=BB_AMBER, font=("Consolas", 8, "bold"), highlightthickness=0, relief=tk.FLAT)
menu_lex["menu"].config(bg=BB_CARD, fg=BB_TEXT, font=("Consolas", 9))
menu_lex.pack(side=tk.RIGHT)

lbl_lex_desc = tk.Label(lexique_box, text=LEXIQUE_BIAIS["COMPTABILITÉ MENTALE"], font=("Segoe UI", 9), bg="#0d1117", fg=BB_TEXT, anchor="w", justify="left", wraplength=610)
lbl_lex_desc.pack(fill=tk.X)

# Démarrage
maj_horloge()
lancer_scan()
fenetre.mainloop()