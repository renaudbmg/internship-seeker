"""Filtrage des titres : block (dur) > keep (signal positif) > exclude (soft)."""

from backend.scraper.base import should_exclude_title, title_matches_any

EXCLUDE = ["senior", "lead", "commercial", "cdi"]
KEEP = ["stage", "alternance", "pfe"]
BLOCK = ["vendeur", "coach", "hôtesse", "éducateur"]


def excl(title):
    return should_exclude_title(title, EXCLUDE, KEEP, BLOCK)


def test_garde_offre_cible():
    assert excl("Stage Data Analyst Sport") is False
    assert excl("Alternance Business Analyst") is False
    assert excl("PFE Data Science") is False


def test_block_l_emporte_sur_keep():
    # « stage » ne sauve PAS un poste bloqué
    assert excl("Stage Vendeur Decathlon") is True
    assert excl("Alternance Coach Sportif") is True
    assert excl("Stage Éducateur Sportif") is True


def test_keep_sauve_de_exclude_soft():
    # « stage » l'emporte sur un terme d'exclusion soft
    assert excl("Stage Responsable Commercial") is False
    # mais sans signal positif, l'exclusion soft s'applique
    assert excl("Responsable Commercial") is True


def test_exclude_soft_senior():
    assert excl("Data Analyst Senior") is True
    assert excl("Lead Data Engineer") is True


def test_word_boundary_evite_faux_positifs():
    # "cdi" ne doit pas matcher "Cdiscount"
    assert title_matches_any("Stage chez Cdiscount", ["cdi"]) is False
    assert title_matches_any("Poste en CDI", ["cdi"]) is True


def test_casse_et_accents_ignores():
    assert title_matches_any("STAGE data", ["stage"]) is True
    assert title_matches_any("Éducateur sportif", ["éducateur"]) is True
