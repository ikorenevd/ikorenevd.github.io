"""Формы для карточек французских глаголов."""

import unicodedata

PRONOUNS = ("je", "tu", "il", "nous", "vous", "ils")
TENSES = ("présent", "imparfait", "passé composé")
PRESENT_ER = ("e", "es", "e", "ons", "ez", "ent")
PRESENT_IR = ("is", "is", "it", "issons", "issez", "issent")
IMPARFAIT = ("ais", "ais", "ait", "ions", "iez", "aient")
VOWELS = "aàâäeéèêëiîïoôöuùûüyÿœ"

# У известных правильных глаголов указан инфинитив; у остальных —
# формы présent, причастие прошедшего времени и, при необходимости, вспомогательный глагол.
REGULAR_ER = frozenset("""
    accepter adorer aider aimer ajouter apporter arrêter arriver avancer bavarder
    brosser changer chanter chercher commencer continuer compter couper danser
    coucher décider demander dépêcher dessiner détester donner écouter emmener emporter enseigner
    entrer envoyer étudier expliquer fermer gagner garder goûter habiller habiter intéresser inviter
    jouer laver laisser lever manger marcher mélanger monter montrer nager nettoyer
    oublier parler partager passer payer penser porter poser préférer préparer
    présenter promener quitter raconter rappeler regarder rencontrer rentrer répéter reposer rester retourner
    retrouver réveiller saluer sauter sembler téléphoner tomber toucher travailler tromper
    traverser trouver utiliser visiter voyager acheter amuser appeler jeter peser
""".split())
REGULAR_IR = frozenset("agir bâtir choisir finir grandir grossir maigrir obéir remplir réussir".split())
IRREGULAR = {
    "aller": ("vais vas va allons allez vont", "allé", "être"),
    "apercevoir": ("aperçois aperçois aperçoit apercevons apercevez aperçoivent", "aperçu"),
    "apprendre": ("apprends apprends apprend apprenons apprenez apprennent", "appris"),
    "attendre": ("attends attends attend attendons attendez attendent", "attendu"),
    "avoir": ("ai as a avons avez ont", "eu"),
    "boire": ("bois bois boit buvons buvez boivent", "bu"),
    "comprendre": ("comprends comprends comprend comprenons comprenez comprennent", "compris"),
    "conduire": ("conduis conduis conduit conduisons conduisez conduisent", "conduit"),
    "connaître": ("connais connais connaît connaissons connaissez connaissent", "connu"),
    "courir": ("cours cours court courons courez courent", "couru"),
    "croire": ("crois crois croit croyons croyez croient", "cru"),
    "descendre": ("descends descends descend descendons descendez descendent", "descendu", "both"),
    "devenir": ("deviens deviens devient devenons devenez deviennent", "devenu", "être"),
    "devoir": ("dois dois doit devons devez doivent", "dû"),
    "dire": ("dis dis dit disons dites disent", "dit"),
    "dormir": ("dors dors dort dormons dormez dorment", "dormi"),
    "écrire": ("écris écris écrit écrivons écrivez écrivent", "écrit"),
    "entendre": ("entends entends entend entendons entendez entendent", "entendu"),
    "être": ("suis es est sommes êtes sont", "été"),
    "faire": ("fais fais fait faisons faites font", "fait"),
    "falloir": ("- - faut - - -", "fallu"),
    "haïr": ("hais hais hait haïssons haïssez haïssent", "haï"),
    "lire": ("lis lis lit lisons lisez lisent", "lu"),
    "mettre": ("mets mets met mettons mettez mettent", "mis"),
    "mourir": ("meurs meurs meurt mourons mourez meurent", "mort", "être"),
    "naître": ("nais nais naît naissons naissez naissent", "né", "être"),
    "offrir": ("offre offres offre offrons offrez offrent", "offert"),
    "ouvrir": ("ouvre ouvres ouvre ouvrons ouvrez ouvrent", "ouvert"),
    "partir": ("pars pars part partons partez partent", "parti", "être"),
    "perdre": ("perds perds perd perdons perdez perdent", "perdu"),
    "pleuvoir": ("- - pleut - - -", "plu"),
    "pouvoir": ("peux peux peut pouvons pouvez peuvent", "pu"),
    "prendre": ("prends prends prend prenons prenez prennent", "pris"),
    "recevoir": ("reçois reçois reçoit recevons recevez reçoivent", "reçu"),
    "répondre": ("réponds réponds répond répondons répondez répondent", "répondu"),
    "revenir": ("reviens reviens revient revenons revenez reviennent", "revenu", "être"),
    "rire": ("ris ris rit rions riez rient", "ri"),
    "savoir": ("sais sais sait savons savez savent", "su"),
    "sentir": ("sens sens sent sentons sentez sentent", "senti"),
    "servir": ("sers sers sert servons servez servent", "servi"),
    "sortir": ("sors sors sort sortons sortez sortent", "sorti", "both"),
    "sourire": ("souris souris sourit sourions souriez sourient", "souri"),
    "souvenir": ("souviens souviens souvient souvenons souvenez souviennent", "souvenu", "être"),
    "suivre": ("suis suis suit suivons suivez suivent", "suivi"),
    "tenir": ("tiens tiens tient tenons tenez tiennent", "tenu"),
    "traduire": ("traduis traduis traduit traduisons traduisez traduisent", "traduit"),
    "vendre": ("vends vends vend vendons vendez vendent", "vendu"),
    "venir": ("viens viens vient venons venez viennent", "venu", "être"),
    "vivre": ("vis vis vit vivons vivez vivent", "vécu"),
    "voir": ("vois vois voit voyons voyez voient", "vu"),
    "vouloir": ("veux veux veut voulons voulez veulent", "voulu"),
}
REFLEXIVE = frozenset("""
    appeler arrêter brosser coucher dépêcher habiller laver lever promener
    réveiller souvenir amuser intéresser préparer reposer tromper
""".split())
REFLEXIVE_NO_AGREEMENT = frozenset("écrire parler rappeler répondre sourire téléphoner".split())
ETRE_ER = frozenset("arriver rester tomber".split())
BOTH_ER = frozenset("entrer monter passer rentrer retourner".split())
ASPIRE_H = ("haï", "halet", "hasard", "hât", "hériss", "heurt", "hiss", "hurl")


def normalized(text):
    return " ".join(unicodedata.normalize("NFC", text).casefold().replace("'", "’").split())


def conjugation_target(card):
    """Определить инфинитив в начале слова или выражения."""
    if card["kind"] not in ("word", "conjugation"):
        return None
    model = card.get("verb_model")
    if model == "none":
        return None
    text = normalized(card["front"])
    reflexive = text.startswith(("se ", "s’"))
    if reflexive:
        text = text[2:] if text.startswith("s’") else text[3:]
    verb = text.split(" ", 1)[0]
    if model and not (verb.isalpha() and verb.endswith(model) and len(verb) > 2):
        raise ValueError(f"Введите инфинитив на -{model} в начале карточки.")
    if reflexive:
        if verb not in REFLEXIVE and verb not in REFLEXIVE_NO_AGREEMENT:
            if model:
                raise ValueError("Для этого возвратного глагола введите формы вручную.")
            return None
    elif verb == "souvenir":
        return None
    if not (model or verb in REGULAR_ER or verb in REGULAR_IR or verb in IRREGULAR):
        return None
    return verb, reflexive, model


def er_present(verb):
    stem = verb[:-2]
    changed = stem
    if verb.endswith(("oyer", "uyer")):
        changed = stem[:-1] + "i"
    elif verb.endswith(("appeler", "jeter")):
        changed = stem + stem[-1]
    else:
        consonants = 2 if stem.endswith(("bl", "br", "cl", "cr", "dr", "fl", "fr",
                                         "gl", "gr", "pl", "pr", "tr", "vr")) else 1
        accent = len(stem) - consonants - 1
        if accent >= 0 and stem[accent] in "eé" and stem[-1] not in VOWELS:
            changed = stem[:accent] + "è" + stem[accent + 1:]
    nous = stem
    if verb.endswith("ger"):
        nous += "e"
    elif verb.endswith("cer"):
        nous = stem[:-1] + "ç"
    stems = (changed, changed, changed, nous, stem, changed)
    return [part + ending for part, ending in zip(stems, PRESENT_ER)]


def verb_forms(verb, model):
    if verb in IRREGULAR:
        forms, participle, *auxiliary = IRREGULAR[verb]
        return forms.split(), participle, auxiliary[0] if auxiliary else "avoir"
    if verb in REGULAR_IR or model == "ir":
        return [verb[:-2] + ending for ending in PRESENT_IR], verb[:-1], "avoir"
    auxiliary = "avoir"
    if verb in ETRE_ER:
        auxiliary = "être"
    elif verb in BOTH_ER:
        auxiliary = "both"
    return er_present(verb), verb[:-2] + "é", auxiliary


def imperfect_forms(verb, present):
    special = {"être": "ét", "falloir": "fall", "pleuvoir": "pleuv"}
    stem = special.get(verb, present[3][:-3])
    forms = []
    for index, ending in enumerate(IMPARFAIT):
        part = stem
        if index in (3, 4):
            if part.endswith("ge"):
                part = part[:-1]
            elif part.endswith("ç"):
                part = part[:-1] + "c"
        forms.append(part + ending if present[index] != "-" else "-")
    return forms


def starts_with_vowel(word, mute_h=True):
    return word[0] in VOWELS or mute_h and word.startswith("h")


def with_pronoun(form, index, reflexive=False, mute_h=True, paired=True):
    pronoun = PRONOUNS[index]
    if paired and index in (2, 5):
        pronoun += "/elle" if index == 2 else "/elles"
    elide = starts_with_vowel(form, mute_h)
    if reflexive:
        reflexive_pronoun = ("me", "te", "se", "nous", "vous", "se")[index]
        separator = " "
        if elide and index not in (3, 4):
            reflexive_pronoun = reflexive_pronoun[:-1]
            separator = "’"
        return pronoun + " " + reflexive_pronoun + separator + form
    return "j’" + form if index == 0 and elide else pronoun + " " + form


def agreed_past(form, participle, index):
    feminine = participle if participle.endswith("e") else participle + "e"
    plural = participle if participle.endswith(("s", "x")) else participle + "s"
    feminine_plural = feminine + "s"
    if index == 2:
        return f"{form} {participle} / elle{form[2:]} {feminine}"
    if index == 5:
        return f"{form} {plural} / elles{form[3:]} {feminine_plural}"
    if index == 3:
        variants = (plural, feminine_plural)
    elif index == 4:
        variants = (participle, feminine, plural, feminine_plural)
    else:
        variants = (participle, feminine)
    return form + " " + " / ".join(dict.fromkeys(variants))


def conjugation_label(target):
    verb, reflexive, _ = target
    if reflexive:
        prefix = "s’" if starts_with_vowel(verb, not verb.startswith(ASPIRE_H)) else "se "
        return prefix + verb
    return verb


def conjugation_rows(target):
    verb, reflexive, model = target
    mute_h = not verb.startswith(ASPIRE_H)
    present, participle, auxiliary = verb_forms(verb, model)
    imperfect = imperfect_forms(verb, present)
    paired = present[0] != "-"
    rows = {}
    for tense in TENSES:
        for index, pronoun in enumerate(PRONOUNS):
            if present[index] == "-":
                continue
            if tense == "passé composé":
                avoir = IRREGULAR["avoir"][0].split()[index]
                etre = IRREGULAR["être"][0].split()[index]
                avoir_form = f"{with_pronoun(avoir, index, paired=paired)} {participle}"
                if reflexive and verb in REFLEXIVE_NO_AGREEMENT:
                    etre_form = f"{with_pronoun(etre, index, reflexive)} {participle}"
                else:
                    etre_form = agreed_past(with_pronoun(etre, index, reflexive, paired=False),
                                            participle, index)
                if reflexive or auxiliary == "être":
                    form = etre_form
                elif auxiliary == "both":
                    form = f"{etre_form} ; {avoir_form}"
                else:
                    form = avoir_form
            else:
                form = (present if tense == "présent" else imperfect)[index]
                form = with_pronoun(form, index, reflexive, mute_h, paired)
            rows[tense, pronoun] = form
    return rows


def format_conjugations(rows):
    blocks = {}
    for (tense, _), form in rows.items():
        blocks.setdefault(tense, [tense.capitalize()]).append(form)
    return "\n\n".join("\n".join(block) for block in blocks.values())


def group_conjugations(cards):
    """Собрать старые карточки отдельных форм и сохранить их идентификаторы."""
    groups = {}
    standalone = {}
    for card in cards:
        if card["kind"] == "word":
            target = conjugation_target(card)
            if target and normalized(card["front"]) == conjugation_label(target):
                standalone.setdefault(normalized(card["front"]), card)
        elif card["kind"] == "conjugation":
            parts = normalized(card["front"]).split(" · ")
            if len(parts) == 3 and parts[1] in TENSES and parts[2] in PRONOUNS:
                groups.setdefault(parts[0], []).append((card, tuple(parts[1:])))

    replacements = {}
    removed = set()
    for verb, entries in groups.items():
        rows = {}
        for card, key in entries:
            tense, pronoun = key
            form = card["back"]
            if pronoun in ("il", "ils") and verb not in ("falloir", "pleuvoir"):
                prefix = pronoun + " "
                shared = tense != "passé composé" or form.startswith(("il a ", "ils ont "))
                if shared and form.startswith(prefix) and " / elle" not in form:
                    form = ("il/elle " if pronoun == "il" else "ils/elles ") + form[len(prefix):]
            if key in rows and form not in rows[key].split("\n"):
                rows[key] += "\n" + form
            else:
                rows.setdefault(key, form)
        ordered = {(tense, person): rows[tense, person] for tense in TENSES
                   for person in PRONOUNS if (tense, person) in rows}
        word = standalone.get(verb)
        card_id = word["id"] if word else entries[0][0]["id"]
        grouped = {"id": card_id, "kind": "conjugation", "front": verb,
                   "back": format_conjugations(ordered)}
        if word:
            grouped["translation"] = word["back"]
            if word.get("example"):
                grouped["example"] = word["example"]
        examples = list(dict.fromkeys(card["example"] for card, _ in entries if card.get("example")))
        if examples:
            grouped["example"] = "\n".join(filter(None, [grouped.get("example"), *examples]))
        old_ids = [card["id"] for card, _ in entries if card["id"] != card_id]
        if old_ids:
            grouped["previous_ids"] = old_ids
        replacements[card_id] = grouped
        removed.update(old_ids)
    return [replacements.get(card["id"], card) for card in cards if card["id"] not in removed]
