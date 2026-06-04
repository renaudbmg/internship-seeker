"""Scoring heuristique : doit classer data/sport/stage > marketing > vente."""

from backend.ai.heuristic import heuristic_score


def test_borne_0_100():
    for title in ["", "Stage Data Analyst Sport SQL Python", "Vendeur Senior"]:
        s = heuristic_score(title, "")
        assert 0 <= s <= 100


def test_data_sport_stage_en_tete():
    cible = heuristic_score("Stage Data Analyst Sport", "SQL Python BigQuery analytics")
    marketing = heuristic_score("Stage Marketing Digital", "community management")
    assert cible > marketing
    assert cible >= 80


def test_data_dans_titre_booste():
    avec = heuristic_score("Data Analyst", "")
    sans = heuristic_score("Assistant polyvalent", "")
    assert avec > sans


def test_signaux_negatifs_penalisent():
    junior = heuristic_score("Stage Data Analyst", "SQL")
    senior = heuristic_score("Data Analyst Senior", "SQL")
    assert junior > senior


def test_description_enrichit_le_score():
    titre_seul = heuristic_score("Stage analytics", "")
    avec_desc = heuristic_score("Stage analytics", "Python SQL dbt BigQuery ETL reporting KPI")
    assert avec_desc >= titre_seul
